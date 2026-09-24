"""案件外发（Webhook 推送）——把需要深度处理的案件推给外部系统（SOAR / SIEM / 工单 / 通知）。

触发：案件顶出、前额叶（系统2）深析报告就绪后，自动 POST 到配置好的 webhook；
也支持手动逐案推送。配置在 backend/webhooks.json，payload 为固定 JSON，下游好解析。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime

import httpx
import jinja2

from app import crud as db
from app.core.paths import WEBHOOKS_PATH

# 可外发的全部字段（报告里的子字段用 "report.xxx" 点号路径单独选择）。
ALL_FIELDS = [
    "correlation_uid", "title", "strength", "status", "verdict",
    "entities", "ips", "alerts",
    "report.verdict", "report.confidence", "report.digest",
    "report.attack_chain", "report.iocs", "report.remediations", "report.unknowns",
]

# 请求体模板环境：ChainableUndefined 让模板引用缺失字段/None 时渲染为空串而非报错；
# autoescape=False 因为输出是请求体不是 HTML。
_ENV = jinja2.Environment(undefined=jinja2.ChainableUndefined, autoescape=False)


def load_webhooks() -> list[dict]:
    try:
        data = json.loads(WEBHOOKS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_webhooks(webhooks: list[dict]) -> None:
    WEBHOOKS_PATH.write_text(json.dumps(webhooks, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(event: str, case_id: int) -> dict | None:
    case = db.get_case(case_id)
    if not case:
        return None
    alerts = db.get_case_alerts(case_id)
    report = db.get_case_report(case_id)
    return {
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "case": {
            "correlation_uid": case["correlation_uid"],
            "title": case["title"],
            "strength": case["strength"],
            "status": case.get("status") or "New",
            "verdict": case.get("verdict") or "",
            "entities": case.get("entities", []),
            "ips": sorted({e["value"] for e in case.get("entities", []) if e.get("type") == "ip"}),
            "alerts": [
                {"time": a["time"], "source": a["source"], "asset": a["asset"],
                 "type": a["type"], "raw": a["raw"], "confidence": a["confidence"]}
                for a in alerts
            ],
            "report": {
                "verdict": report.get("verdict", ""), "confidence": report.get("confidence", ""),
                "digest": report.get("digest", ""), "attack_chain": report.get("attack_chain", []),
                "iocs": report.get("iocs", []), "remediations": report.get("remediations", []),
                "unknowns": report.get("unknowns", []),
            } if report else None,
        },
    }


def _filter(payload: dict, fields: list[str] | None) -> dict:
    """按 webhook 的 fields 逐字段裁剪 payload。

    fields=None（旧配置没这字段）→ 默认全量；fields 是字段名列表，报告子字段用
    "report.xxx" 点号路径（如 "report.attack_chain"）。event/timestamp 恒在。
    """
    if fields is None:
        fields = ALL_FIELDS
    case = payload["case"]
    out_case: dict = {}
    for f in fields:
        if f in ("correlation_uid", "title", "strength", "status", "verdict", "entities", "ips", "alerts"):
            out_case[f] = case[f]
        elif f.startswith("report."):
            sub = f[len("report."):]
            out_case.setdefault("report", {})[sub] = (case.get("report") or {}).get(sub)
    return {"event": payload["event"], "timestamp": payload["timestamp"], "case": out_case}


def _deliver(wb: dict, payload: dict) -> bool:
    headers = {"Content-Type": "application/json"}
    if wb.get("token"):
        headers["Authorization"] = f"Bearer {wb['token']}"
    headers.update(wb.get("headers") or {})  # 自定义头（-H）覆盖默认头
    try:
        # 有 body 模板 → 渲染为原始请求体；否则回退到固定 JSON 信封（按 fields 裁剪）
        if wb.get("body"):
            content = _ENV.from_string(wb["body"]).render(**payload)
            kwargs = {"data": content}
        else:
            kwargs = {"json": _filter(payload, wb.get("fields"))}
        # trust_env=False：外发目标多为内网/本地下游，直连不走代理（也避免 httpx 解析 socks 代理报错）
        with httpx.Client(trust_env=False, timeout=10) as client:
            resp = client.post(wb.get("url", ""), headers=headers, **kwargs)
        ok = 200 <= resp.status_code < 400
        db.insert_audit("webhook", wb.get("name", ""),
                        json.dumps({"event": payload.get("event"), "status": resp.status_code, "ok": ok},
                                   ensure_ascii=False))
        return ok
    except Exception as e:
        db.insert_audit("webhook", wb.get("name", ""),
                        json.dumps({"event": payload.get("event"), "error": str(e)}, ensure_ascii=False))
        return False


def _matches(wb: dict, event: str) -> bool:
    if not wb.get("enabled", True):
        return False
    trig = wb.get("trigger", "escalated")
    if trig == "manual":
        return False
    if trig == "escalated":
        return event == "escalated"
    return True  # "all"


def notify(event: str, case_id: int) -> None:
    """fire-and-forget：按 trigger 匹配后推送，不阻塞调用方（字段裁剪/模板渲染在 _deliver 内）。"""
    payload = _payload(event, case_id)
    if not payload:
        return
    for wb in load_webhooks():
        if _matches(wb, event):
            threading.Thread(target=_deliver, args=(wb, payload), daemon=True).start()


def push_case(case_id: int) -> list[dict]:
    """手动推送该案到所有 enabled webhook（同步，返回逐目标结果）。"""
    payload = _payload("case_pushed", case_id)
    if not payload:
        return []
    results = []
    for wb in load_webhooks():
        if wb.get("enabled", True):
            results.append({"name": wb.get("name", ""), "url": wb.get("url", ""),
                            "ok": _deliver(wb, payload)})
    return results


def test_webhook(wb: dict) -> bool:
    payload = {
        "event": "test", "timestamp": datetime.now().isoformat(timespec="seconds"),
        "case": {"correlation_uid": "__test__", "message": "Soma外发测试"},
    }
    return _deliver(wb, payload)
