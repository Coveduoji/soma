"""Kafka 消息解析适配器——把 Kafka 消息转换成统一信号 schema。

支持两种消息：
1. **Filebeat JSON**（`{"message": "...", "fields": {"source": "waf"}}`）——提取 message + 来源，走配置解析。
2. **原始 syslog 文本**（RFC3164/5424）——复用 `prototype/syslog.py` 的 `parse_line`。

产出与现有 syslog 解析一致的 `{time, source, asset, type, raw, [entities, severity, attack_result]}`。
"""
from __future__ import annotations

import json

import parsers  # prototype/parsers.py
import syslog as syslog_parser  # prototype/syslog.py（经 app/__init__.py 的 sys.path shim）

# Filebeat fields.source（英文）→ 中文来源名（对应 syslog_parsers.json 的键）
SOURCE_MAP = {"tianyan": "天眼", "waf": "WAF"}


def _parse_configured_with_source(message: str, src_name: str) -> dict | None:
    """用指定来源的解析规则解析一条日志行。"""
    cfg = syslog_parser._load_parsers().get(src_name)
    if not cfg:
        return None
    body = parsers.strip_syslog_header(message) if cfg.get("strip_syslog") else message
    return parsers.parse_configured(body, message, src_name, cfg)


def parse(msg: bytes | str, src_ip: str = "") -> dict | None:
    """解析一条 Kafka 消息 → 统一信号 dict；解析不出返回 None。"""
    if isinstance(msg, bytes):
        text = msg.decode("utf-8", "replace")
    else:
        text = msg
    text = text.strip()
    if not text:
        return None

    # Filebeat JSON：{"message": "...", "fields": {"source": "waf"}}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict) and data.get("message"):
            message = str(data["message"]).strip()
            source = str((data.get("fields") or {}).get("source", "") or "")
            src_name = SOURCE_MAP.get(source, "")
            if src_name and message:
                sig = _parse_configured_with_source(message, src_name)
                if sig is not None:
                    return sig
            # 来源未识别或配置解析未命中 → 回退原始文本解析
            return syslog_parser.parse_line(message, src_ip)

    # 原始 syslog 文本
    return syslog_parser.parse_line(text, src_ip)
