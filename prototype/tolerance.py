"""免疫耐受（免疫层的压误报件）——杏仁核的配套，README 说二者「不能单独上」。

误报反馈回路：把被确认是「正常业务」的信号，按「签名」写进白名单（signature.py 里的
告警形状，掩码掉 IP/哈希/数字，保留主机/账号/描述）。下次杏仁核再看到同形状的信号就
直接静默，连便宜模型都不用叫——既压误报又省算力。白名单持久化在 data/tolerance.json。

比 (asset, type) 更细：签名区分「svc_backup 登录跳板机」和「svc_backup 登录数据库」，
只静默前者，不再漏掉同一资产上的真实攻击。

误杀闭环：白名单条目带 created_at，可配 TTL 到期（tolerance_ttl_days，0=永久），到期后
自动失效重新研判，避免「永久静默」漏掉真实攻击；分析师「放回」时由 API 层移除对应签名。
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from signature import signature

# 路径：SOMA_DATA_DIR 设置时规则进数据卷（与 memory/feedback 同级，Docker 下重启不丢），
# 否则回落 prototype/data/（prototype 零依赖独立可跑）。
_data_dir = os.environ.get("SOMA_DATA_DIR", "").strip()
if _data_dir:
    _DIR = Path(_data_dir).expanduser() / "data"
else:
    _DIR = Path(__file__).resolve().parent / "data"
TOLERANCE_PATH = _DIR / "tolerance.json"
_LEGACY_PATH = Path(__file__).resolve().parent / "data" / "tolerance.json"

_lock = threading.Lock()
_cache: dict = {"mtime": -1.0, "data": None}


def _read_entries() -> dict:
    """直接读盘（不经缓存），供写路径在锁内使用；含旧路径首次迁移。"""
    if TOLERANCE_PATH != _LEGACY_PATH and not TOLERANCE_PATH.exists() and _LEGACY_PATH.exists():
        import shutil
        TOLERANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_PATH, TOLERANCE_PATH)
    if not TOLERANCE_PATH.exists():
        return {}
    with open(TOLERANCE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    entries: dict[str, dict] = {}
    if isinstance(data, dict):
        # 新格式：{sig: {"created_at": ts}}
        for sig, meta in data.items():
            if isinstance(sig, str):
                entries[sig] = meta if isinstance(meta, dict) else {"created_at": time.time()}
    elif isinstance(data, list):
        # 旧格式迁移：str 元素 → 带 now；[asset, type] 列表 → 丢弃（= 重置，不可逆）
        now = time.time()
        for e in data:
            if isinstance(e, str):
                entries[e] = {"created_at": now}
    return entries


def _write_entries(entries: dict) -> None:
    """原子写：临时文件 + os.replace，避免入库读到半截 JSON。"""
    TOLERANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOLERANCE_PATH.with_name(TOLERANCE_PATH.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TOLERANCE_PATH)
    _cache["mtime"] = -1.0  # 缓存失效


def load_tolerance() -> dict:
    """读白名单（mtime 缓存，避免流式入库每条告警都读盘）。返回 {sig: {"created_at": ts}}。"""
    mtime = TOLERANCE_PATH.stat().st_mtime if TOLERANCE_PATH.exists() else -1.0
    if _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    data = _read_entries()
    _cache["mtime"] = mtime
    _cache["data"] = data
    return data


def save_tolerance(entries: dict) -> None:
    """直接原子写白名单（写操作优先用 learn_signatures / remove_signature / clear_entries）。"""
    _write_entries(entries)


def is_tolerated(signal: dict, entries: dict, ttl_seconds: float = 0) -> bool:
    """同「形状」的信号已在白名单且未过期 → 已耐受，直接静默。ttl_seconds<=0 表示永久。"""
    sig = signature(signal.get("source", ""), signal.get("type", ""),
                    signal.get("raw", ""), signal.get("asset", ""))
    if sig not in entries:
        return False
    if ttl_seconds and ttl_seconds > 0:
        meta = entries[sig]
        created = meta.get("created_at", 0) if isinstance(meta, dict) else 0
        if time.time() - created > ttl_seconds:
            return False
    return True


def learn(entries: dict, sigs: list[str], now: float | None = None) -> list[str]:
    """把新签名加进白名单，返回本次新增的。只收签名字符串（过滤旧 (asset,type) 元组）。"""
    now = time.time() if now is None else now
    new = [s for s in sigs if isinstance(s, str) and s not in entries]
    for s in new:
        entries[s] = {"created_at": now}
    return new


# ---- 原子操作（锁内 load-modify-save，替换调用点的手动三步）----


def learn_signatures(sigs: list[str]) -> list[str]:
    with _lock:
        entries = _read_entries()
        new = learn(entries, sigs)
        if new:
            _write_entries(entries)
        return new


def remove_signature(sig: str) -> bool:
    with _lock:
        entries = _read_entries()
        removed = sig in entries
        entries.pop(sig, None)
        _write_entries(entries)
        return removed


def clear_entries() -> None:
    with _lock:
        _write_entries({})
