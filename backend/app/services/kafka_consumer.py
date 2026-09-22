"""Kafka 消费者线程组——消费日志云平台打到 Kafka 的日志，解析后增量入库。

与 syslog_server 走同一条管道（pipeline.process_signal）。无 Kafka 环境变量时静默跳过，
行为退化为现有 syslog 直收。
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime

import syslog as syslog_parser  # prototype/syslog.py，用于注入数据目录的解析配置路径

from app import crud as db
from app.core import logging as logging_setup
from app.services import pipeline, state
from app.services.kafka_adapter import parse

logger = logging_setup.get_logger("kafka")

_enabled = False
_consumer_thread: threading.Thread | None = None
_last_consume = None  # 最近一次成功消费的时间戳
_consumed = 0  # 累计成功消费条数
_failed = 0  # 累计处理失败条数（已记死信 + 审计，不静默丢弃）


def _dead_letter_path():
    return state.data_dir() / "data" / "kafka_dead_letter.jsonl"


def _record_dead_letter(raw: str, error: str) -> None:
    """把处理失败的消息写进死信文件（JSONL，可重放），绝不静默丢弃。"""
    path = _dead_letter_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(), "error": error, "message": raw},
                               ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("写死信文件失败")


def dead_letter_count() -> int:
    """死信文件里待重放的条数。"""
    path = _dead_letter_path()
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in open(path, encoding="utf-8"))
    except Exception:
        return 0


def list_dead_letters() -> list[dict]:
    """死信条目（供 UI 查看）。"""
    path = _dead_letter_path()
    if not path.exists():
        return []
    out = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                out.append({"time": "", "error": "记录损坏", "message": line})
    except Exception:
        pass
    return out


def replay_dead_letter() -> dict:
    """重放死信：逐条 parse + process_signal，成功的移除，失败的保留。"""
    path = _dead_letter_path()
    if not path.exists():
        return {"replayed": 0, "failed": 0, "remaining": 0}
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    remaining: list[str] = []
    replayed = failed = 0
    for line in lines:
        try:
            rec = json.loads(line)
            sig = parse(rec.get("message", ""))
            if sig is None:
                failed += 1
                remaining.append(line)
                continue
            pipeline.process_signal(sig)
            replayed += 1
        except Exception as e:
            logger.warning("死信重放失败：%s", e)
            failed += 1
            remaining.append(line)
    if remaining:
        path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return {"replayed": replayed, "failed": failed, "remaining": len(remaining)}


def config() -> dict:
    """读 Kafka 连接配置（环境变量，连外部已有 Kafka 只需改这里）。"""
    return {
        "servers": os.environ.get("NEUROIMMUNE_KAFKA_BOOTSTRAP_SERVERS", "").strip(),
        "topic": os.environ.get("NEUROIMMUNE_KAFKA_TOPIC", "").strip(),
        "group": os.environ.get("NEUROIMMUNE_KAFKA_GROUP", "neuroimmune").strip(),
        "auto_offset_reset": os.environ.get("NEUROIMMUNE_KAFKA_AUTO_OFFSET_RESET", "earliest").strip(),
    }


def status() -> dict:
    """供 /api/health 读取：消费者存活 + 累计消费 + 最近消费时间。"""
    return {
        "enabled": _enabled,
        "alive": _consumer_thread is not None and _consumer_thread.is_alive(),
        "consumed": _consumed,
        "failed": _failed,
        "last_consume": _last_consume,
    }


def start() -> None:
    global _enabled, _consumer_thread
    cfg = config()
    if not cfg["servers"] or not cfg["topic"]:
        logger.info("未配置 Kafka（NEUROIMMUNE_KAFKA_BOOTSTRAP_SERVERS / NEUROIMMUNE_KAFKA_TOPIC），跳过 Kafka 消费")
        return

    # 复用 syslog 解析器的来源/解析配置（数据目录播种 + 路径注入），与 syslog 直收一致。
    state.get_sources_config()
    state.get_parsers_config()
    syslog_parser._SOURCES_PATH = str(state.SOURCES_PATH)
    syslog_parser._PARSERS_PATH = str(state.PARSERS_PATH)

    def run() -> None:
        global _last_consume, _consumed, _failed
        while True:
            try:
                from kafka import KafkaConsumer
                consumer = KafkaConsumer(
                    cfg["topic"],
                    bootstrap_servers=cfg["servers"],
                    group_id=cfg["group"],
                    auto_offset_reset=cfg["auto_offset_reset"],
                    enable_auto_commit=False,  # 手动提交：成功才提交；失败记死信后再提交，避免毒消息卡死
                    value_deserializer=lambda m: m.decode("utf-8", "replace"),
                )
                logger.info("Kafka 消费者已连接 %s，topic=%s", cfg["servers"], cfg["topic"])
                for msg in consumer:
                    sig = parse(msg.value)
                    if sig is not None:
                        try:
                            pipeline.process_signal(sig)
                            _consumed += 1
                            _last_consume = time.time()
                        except Exception as e:
                            logger.exception("Kafka 信号处理失败")
                            _failed += 1
                            _record_dead_letter(msg.value, str(e))
                            db.insert_audit("kafka_failed", f"signal {sig.get('asset', '')}", str(e)[:200])
                    consumer.commit()
            except Exception:
                logger.exception("Kafka 消费异常，5 秒后重连")
                time.sleep(5)

    _consumer_thread = threading.Thread(target=run, daemon=True)
    _consumer_thread.start()
    _enabled = True
    logger.info("Kafka 消费线程已启动：%s topic=%s", cfg["servers"], cfg["topic"])
