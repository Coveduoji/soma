"""配置驱动的多源告警解析（方案 C 的运行时部分）。

用声明式解析配置把非标准告警日志解析成统一 signal。两种原语：
- dissect：定长字段，delimiter 切分，按 fields 顺序映射字段名（天眼 |! 定长）
- kv：key/value 对，field_split 分键值对、value_split 分键值（WAF 应用防护 / 天眼 key:value）

归一化产出 signal dict {time, source, asset, type, raw, entities}，entities 为精确实体
[{type, value}]，供拼链直接使用——消除正则实体抽取把版本号（4.6.7.8 / Chrome 138.0.0.0）
误当 IP 的噪声。

零依赖，标准库实现。prototype 独立跑时不依赖 backend。
"""
from __future__ import annotations

import datetime
import re


# ---- 时间归一化 ----

def normalize_time(v) -> str:
    """三种时间形态 → 'YYYY-MM-DD HH:MM:SS'：秒级 Unix、毫秒级 Unix、ISO 字符串。
    解析不出返回当前时间。"""
    if v is None:
        return _now()
    s = str(v).strip()
    if not s or s in ("-", "0"):
        return _now()
    if s.isdigit():
        n = int(s)
        if n >= 10_000_000_000:  # 毫秒级
            n //= 1000
        try:
            return datetime.datetime.fromtimestamp(n).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return _now()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return _now()


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---- 剥 RFC3164 头 ----

_SYSLOG_HEAD = re.compile(
    r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+:\s?(.*)$", re.DOTALL
)


def strip_syslog_header(line: str) -> str:
    """剥 RFC3164 头（Mmm dd hh:mm:ss host tag: msg），剥不掉返回原行。"""
    m = _SYSLOG_HEAD.match(line)
    return m.group(1) if m else line


# ---- parser 原语 ----

def parse_dissect(line: str, delimiter: str, fields: list[str]) -> dict:
    """按 delimiter 切分，按 fields 顺序映射；缺省字段补空、多余字段丢弃。"""
    parts = line.split(delimiter)
    return {name: (parts[i].strip() if i < len(parts) else "") for i, name in enumerate(fields)}


def parse_kv(line: str, field_split: str, value_split: str) -> dict:
    """key/value 对：field_split 分对、value_split 分键值（partition 取第一个分隔符，
    这样值里再出现 value_split 也不会截断关键字段——如 WAF 的 UA 值里含 '/'）。"""
    out: dict = {}
    for pair in line.split(field_split):
        pair = pair.strip()
        if not pair:
            continue
        if value_split in pair:
            k, _, v = pair.partition(value_split)
            out[k.strip()] = v.strip()
        else:
            out[pair] = ""
    return out


# ---- 配置解析 ----

def _match_rule(rule: dict, body: str) -> bool:
    m = (rule or {}).get("match", "")
    if isinstance(m, str) and m.startswith("startswith:"):
        return body.startswith(m[len("startswith:"):])
    return True  # 无 match 或未知类型：兜底规则（放在 parsers 列表最后）


_BRACKET_KV_HEAD = re.compile(r"^(\S+)\s+\[[^\]]*\]\s+\[device\]\s*\[(.*)\]$")


def strip_bracket_kv(line: str) -> tuple[str, str] | None:
    """剥「时间戳 [级别] [device] [」前缀和「]」后缀，返回 (时间戳, kv 正文)。"""
    m = _BRACKET_KV_HEAD.match((line or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _normalize(value, mapping: dict | None):
    """取值归一化：value 经 mapping 映射到标准枚举；未命中返回 None（视为缺失）。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if mapping is None:
        return s  # 无归一化表，原样返回
    if s in mapping:
        return mapping[s]
    for k, mapped in mapping.items():
        if str(k).strip().lower() == s.lower():
            return mapped
    return None


def parse_configured(body: str, raw: str, src_name: str, cfg: dict) -> dict | None:
    """按来源配置解析告警。命中返回 signal dict，未命中返回 None。

    body：剥头后的消息体（strip_syslog 为真时），否则为整行；raw 始终是完整原始行。
    """
    for rule in (cfg or {}).get("parsers", []):
        if rule.get("enabled") is False:  # 停用的规则跳过，保留配置不删除
            continue
        if not _match_rule(rule, body):
            continue

        # 剥前缀：`时间戳 [级别] [device] [ ... ]` → 时间戳 + kv 正文
        timestamp = ""
        parse_body = body
        if rule.get("strip_prefix") == "bracket_kv":
            parsed = strip_bracket_kv(body)
            if parsed is None:
                continue  # 格式不匹配，跳过该规则
            timestamp, parse_body = parsed

        rtype = rule.get("type", "")
        if rtype == "dissect":
            fields = parse_dissect(parse_body, rule.get("delimiter", ""), rule.get("fields", []))
        elif rtype == "kv":
            fields = parse_kv(parse_body, rule.get("field_split", ""), rule.get("value_split", ""))
        else:
            continue

        mp = rule.get("map", {})
        entities = []
        for fname, etype in mp.get("entities", []):
            val = fields.get(fname, "").strip()
            if val:
                entities.append({"type": etype, "value": val})

        # time 字段：map 的 time 指向 "_timestamp" 时用剥前缀得到的时间戳
        time_field = mp.get("time", "")
        time_val = timestamp if time_field == "_timestamp" else fields.get(time_field)

        result = {
            "time": normalize_time(time_val),
            "source": src_name,
            "asset": fields.get(mp.get("asset", ""), "").strip(),
            "type": fields.get(mp.get("type", ""), "").strip() or rtype,
            "raw": raw,
            "entities": entities,
        }

        # 威胁等级 / 攻击结果：字段名 + 取值归一化表，归一失败不产出（交给提醒逻辑）
        if "severity" in mp:
            sv = _normalize(fields.get(mp["severity"]), mp.get("severity_map"))
            if sv is not None:
                result["severity"] = sv
        if "attack_result" in mp:
            ar = _normalize(fields.get(mp["attack_result"]), mp.get("attack_result_map"))
            if ar is not None:
                result["attack_result"] = ar

        return result
    return None
