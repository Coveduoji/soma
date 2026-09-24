"""固有免疫（免疫层）——规则引擎，只会认见过的，但秒拦、不花钱。

把「已确认的攻击模式」按签名写进规则（signature.py 的告警形状）；下次信号命中同形状，
直接在边缘秒拦——连杏仁核都不用叫，系统2 更不用醒。

与免疫耐受（tolerance.py）对称：耐受记「已知好」→ 静默，固有免疫记「已知坏」→ 秒拦。
规则持久化在 data/innate_rules.json，签名匹配（比 (asset, type) 更细）。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from signature import signature

# 路径：SOMA_DATA_DIR 设置时规则进数据卷（与 memory/feedback 同级，Docker 下重启不丢），
# 否则回落 prototype/data/（prototype 零依赖独立可跑）。
_data_dir = os.environ.get("SOMA_DATA_DIR", "").strip()
if _data_dir:
    _DIR = Path(_data_dir).expanduser() / "data"
else:
    _DIR = Path(__file__).resolve().parent / "data"
INNATE_PATH = _DIR / "innate_rules.json"
_LEGACY_PATH = Path(__file__).resolve().parent / "data" / "innate_rules.json"

_lock = threading.Lock()
_cache: dict = {"mtime": -1.0, "data": None}


def _read_rules() -> set[str]:
    """直接读盘（不经缓存），供写路径在锁内使用；含旧路径首次迁移。"""
    if INNATE_PATH != _LEGACY_PATH and not INNATE_PATH.exists() and _LEGACY_PATH.exists():
        import shutil
        INNATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_PATH, INNATE_PATH)
    if not INNATE_PATH.exists():
        return set()
    with open(INNATE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # 只收签名字符串；旧格式 [asset, type] 列表会被过滤掉（= 重置，不可逆）
    return {e for e in data if isinstance(e, str)}


def _write_rules(rules: set[str]) -> None:
    """原子写：临时文件 + os.replace，避免入库读到半截 JSON。"""
    INNATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = INNATE_PATH.with_name(INNATE_PATH.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(rules), f, ensure_ascii=False, indent=2)
    os.replace(tmp, INNATE_PATH)
    _cache["mtime"] = -1.0  # 缓存失效


def load_rules() -> set[str]:
    """读规则（mtime 缓存，避免流式入库每条告警都读盘）。"""
    mtime = INNATE_PATH.stat().st_mtime if INNATE_PATH.exists() else -1.0
    if _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    data = _read_rules()
    _cache["mtime"] = mtime
    _cache["data"] = data
    return data


def save_rules(rules: set[str]) -> None:
    """直接原子写规则（写操作优先用 add_signatures / remove_signature / clear_rules）。"""
    _write_rules(rules)


def match(signal: dict, rules: set[str]) -> bool:
    """同「形状」的信号已在规则里 → 已知坏，边缘秒拦。"""
    return signature(signal.get("source", ""), signal.get("type", ""),
                     signal.get("raw", ""), signal.get("asset", "")) in rules


def add(rules: set[str], sigs: list[str]) -> list[str]:
    """把新的签名加进规则，返回本次新增的。"""
    new = [s for s in sigs if s not in rules]
    rules.update(new)
    return new


# ---- 原子操作（锁内 load-modify-save，替换调用点的手动三步）----


def add_signatures(sigs: list[str]) -> list[str]:
    with _lock:
        rules = _read_rules()
        new = add(rules, sigs)
        if new:
            _write_rules(rules)
        return new


def remove_signature(sig: str) -> bool:
    with _lock:
        rules = _read_rules()
        removed = sig in rules
        rules.discard(sig)
        _write_rules(rules)
        return removed


def clear_rules() -> None:
    with _lock:
        _write_rules(set())
