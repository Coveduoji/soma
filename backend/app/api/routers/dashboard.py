"""看板 API：省/学/调汇总 + 风险旋钮 + 被抑制审计 + 入库。"""
from __future__ import annotations

import json
from datetime import datetime

import os

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import deps
import config
from app import crud as db
import innate
import llm
from app.services import pipeline
from app.services import report
from app.services import state
import tolerance
from app.services import webhook
from signature import signature
from app.schemas import KnobSet

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(deps.require_user)])


@router.get("/dashboard")
def dashboard():
    tol = tolerance.load_tolerance()
    rules = innate.load_rules()
    knob = state.get_knob(state.get_knob_name())
    return {
        "counts": db.counts(),
        "knob": {"name": knob.name, "suppress_below": knob.suppress_below,
                 "escalate_above": knob.escalate_above, "budget": knob.budget},
        "presets": state.get_all_presets(),
        "tolerance": sorted(tol),
        "innate": sorted(rules),
    }


@router.get("/trend")
def trend(range: str = "24h"):
    """告警流量趋势（时间桶序列）。range: 24h / 7d / 30d。"""
    ranges = {"24h": (24, 3600), "7d": (168, 21600), "30d": (720, 86400)}
    hours, bucket = ranges.get(range, ranges["24h"])
    return {"range": range, "buckets": db.alert_trend(hours, bucket)}


@router.get("/knob")
def get_knob():
    knob = state.get_knob(state.get_knob_name())
    return {"knob": state.get_knob_name(), "suppress_below": knob.suppress_below,
            "escalate_above": knob.escalate_above, "budget": knob.budget}


@router.put("/knob", dependencies=[Depends(deps.require_perm("config"))])
def set_knob(body: KnobSet):
    if body.knob not in config.PRESETS:
        return {"error": f"未知档位 {body.knob}"}
    state.set_knob_name(body.knob)
    return get_knob()


@router.get("/suppressed")
def suppressed():
    """被抑制的告警（完整落库，可研判）。"""
    return db.list_suppressed_alerts()


@router.post("/tolerance/remove", dependencies=[Depends(deps.require_perm("triage"))])
def tolerance_remove(body: dict):
    """从免疫耐受白名单删一条签名。"""
    sig = (body or {}).get("signature", "")
    removed = tolerance.remove_signature(sig)
    db.insert_audit("tolerance_remove", sig, json.dumps({"removed": removed}, ensure_ascii=False))
    return {"remaining": sorted(tolerance.load_tolerance())}


@router.post("/tolerance/clear", dependencies=[Depends(deps.require_perm("triage"))])
def tolerance_clear():
    tolerance.clear_entries()
    db.insert_audit("tolerance_clear", "all", "")
    return {"remaining": []}


@router.post("/innate/remove", dependencies=[Depends(deps.require_perm("triage"))])
def innate_remove(body: dict):
    """从固有免疫规则删一条签名。"""
    sig = (body or {}).get("signature", "")
    removed = innate.remove_signature(sig)
    db.insert_audit("innate_remove", sig, json.dumps({"removed": removed}, ensure_ascii=False))
    return {"remaining": sorted(innate.load_rules())}


@router.post("/innate/clear", dependencies=[Depends(deps.require_perm("triage"))])
def innate_clear():
    innate.clear_rules()
    db.insert_audit("innate_clear", "all", "")
    return {"remaining": []}


@router.get("/thalamus")
def list_alerts(source: str | None = None, suppressed: str | None = None, q: str | None = None,
                sort: str = "time", limit: int = 50, offset: int = 0):
    """丘脑（原始告警流）：全部入库告警（含被抑制），支持来源/抑制状态/关键词 + 分页。"""
    items = db.list_all_alerts(source, suppressed, q, sort, limit, offset)
    total = db.count_all_alerts(source, suppressed, q)
    return {"items": items, "total": total, "sources": db.get_distinct_sources()}


@router.get("/audit")
def list_audit(action: str | None = None, limit: int = 200):
    """决策留痕：single_signal_skipped / budget_blocked / 处置等审计日志。"""
    return {"items": db.list_audit(action)[:limit]}


@router.post("/suppressed/{alert_id}/restore", dependencies=[Depends(deps.require_perm("triage"))])
def restore(alert_id: int):
    """把一条被误压的告警放回：重新上板、归案、触发深度分析。

    放回同时纠正白名单误杀——若该告警签名在白名单里（被免疫耐受静默），
    移除它，避免同形状告警反复被静默。
    """
    alert = db.get_alert(alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    sig = signature(alert["source"], alert["type"], alert["raw"], alert["asset"])
    untolerated = tolerance.remove_signature(sig)
    signal = {"time": alert["time"], "source": alert["source"], "asset": alert["asset"],
              "type": alert["type"], "raw": alert["raw"]}
    result = pipeline.restore_signal(signal)
    db.delete_alert(alert_id)
    changes = {"from_alert": alert_id}
    if untolerated:
        changes["untolerated"] = sig
    db.insert_audit("restored", f'{alert["asset"]} {alert["type"]}',
                    json.dumps(changes, ensure_ascii=False))
    return result


@router.post("/alerts/{alert_id}/disposition", dependencies=[Depends(deps.require_perm("triage"))])
def alert_disposition(alert_id: int, body: dict | None = None):
    """对单条告警标记误报/真阳性，回写对应规则（比整案一刀切更细粒度）。"""
    alert = db.get_alert(alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    verdict = (body or {}).get("verdict", "")
    reason = (body or {}).get("reason", "")
    sig = signature(alert["source"], alert["type"], alert["raw"], alert["asset"])
    learned = []
    if verdict == "False Positive":
        learned = tolerance.learn_signatures([sig])
        if sig in innate.load_rules():
            db.insert_audit("tolerance_conflict", f"alert {alert_id}",
                            json.dumps({"conflicts": [sig], "reason": reason}, ensure_ascii=False))
    elif verdict == "True Positive":
        learned = innate.add_signatures([sig])
        if sig in tolerance.load_tolerance():
            db.insert_audit("innate_conflict", f"alert {alert_id}",
                            json.dumps({"conflicts": [sig], "reason": reason}, ensure_ascii=False))
    else:
        raise HTTPException(400, "verdict 必须是 False Positive 或 True Positive")
    db.set_alert_verdict(alert_id, verdict)
    db.insert_audit("alert_disposition", f"alert {alert_id}",
                    json.dumps({"verdict": verdict, "learned": learned, "reason": reason}, ensure_ascii=False))
    db.append_feedback({
        "type": "false_positive" if verdict == "False Positive" else "true_positive",
        "entities": [[alert["asset"], alert["type"]]],
        "reason": reason,
        "time": datetime.now().isoformat(),
    })
    return {"alert_id": alert_id, "verdict": verdict}


@router.get("/entities/cases")
def entity_cases(type: str, value: str):
    """反查：某个实体出现在哪些案件里。"""
    return db.cases_for_entity(type, value)


@router.get("/hippocampus/events")
def graph_events(type: str, value: str, type2: str | None = None, value2: str | None = None,
                 source: str | None = None, sort: str = "time", limit: int = 200, offset: int = 0):
    """海马体节点/边的关联事件（一次调用拿全量事件，带筛选 + 排序 + 分页）。"""
    if type2 and value2:
        items = db.get_alerts_for_entity_pair(type, value, type2, value2, source, sort, limit, offset)
        total = db.count_alerts_for_entity_pair(type, value, type2, value2, source)
    else:
        items = db.get_alerts_for_entity(type, value, source, sort, limit, offset)
        total = db.count_alerts_for_entity(type, value, source)
    return {"items": items, "total": total, "sources": db.get_distinct_sources()}


@router.get("/hippocampus")
def global_graph():
    """海马体（实体关系图）：所有实体为点、共现为边，点和边都带关联案件。"""
    artifacts = db.get_all_artifacts()
    links = db.get_all_alert_artifacts()
    uid_map = db.get_case_uid_map()

    idx = {a["id"]: i for i, a in enumerate(artifacts)}
    nodes = [{"id": i, "type": a["type"], "value": a["value"], "cases": set(), "degree": 0}
             for i, a in enumerate(artifacts)]

    alert_arts: dict[int, list[int]] = {}
    alert_case: dict[int, int] = {}
    for l in links:
        alert_arts.setdefault(l["alert_id"], []).append(l["artifact_id"])
        alert_case[l["alert_id"]] = l["case_id"]

    edges: dict[tuple[int, int], set[int]] = {}
    for aid, art_ids in alert_arts.items():
        case_id = alert_case[aid]
        for a in art_ids:
            nodes[idx[a]]["cases"].add(case_id)
        for i in range(len(art_ids)):
            for j in range(i + 1, len(art_ids)):
                x, y = sorted((idx[art_ids[i]], idx[art_ids[j]]))
                if x == y:
                    continue
                edges.setdefault((x, y), set()).add(case_id)

    # degree = 唯一邻居数（不是共现次数）
    for x, y in edges:
        nodes[x]["degree"] += 1
        nodes[y]["degree"] += 1

    def _uids(case_ids: set) -> list[str]:
        return [uid_map[c] for c in sorted(case_ids) if c in uid_map]

    return {
        "nodes": [{"id": n["id"], "type": n["type"], "value": n["value"],
                   "cases": _uids(n["cases"]), "degree": n["degree"]} for n in nodes],
        "edges": [{"source": s, "target": t, "cases": _uids(cs)} for (s, t), cs in edges.items()],
    }


@router.post("/reset", dependencies=[Depends(deps.require_perm("maintenance"))])
def reset():
    """手动清库（重新开始）。"""
    db.reset()
    return {"status": "reset"}


@router.post("/consolidate", dependencies=[Depends(deps.require_perm("maintenance"))])
def consolidate_now():
    """手动触发夜间巩固（睡眠巩固：SQLite → 检索记忆，供系统2 RAG）。"""
    import nightly
    return nightly.consolidate()


@router.get("/presets")
def presets():
    return state.get_all_presets()


@router.get("/freq")
def get_freq():
    return state.get_freq_config()


@router.put("/freq", dependencies=[Depends(deps.require_perm("config"))])
def set_freq(body: dict):
    cfg = state.get_freq_config()
    state.set_freq_config(
        window=int(body.get("window", cfg["window"])),
        threshold=int(body.get("threshold", cfg["threshold"])),
        demote=float(body.get("demote", cfg["demote"])),
    )
    return state.get_freq_config()


@router.get("/mode")
def get_mode():
    return {"mode": state.get_model_mode()}


@router.put("/mode", dependencies=[Depends(deps.require_perm("config"))])
def set_mode(body: dict):
    mode = (body or {}).get("mode", "")
    if mode not in ("auto", "mock", "real"):
        raise HTTPException(400, f"未知模式 {mode}")
    state.set_model_mode(mode)
    return {"mode": state.get_model_mode()}


@router.get("/gating")
def get_gating():
    return state.get_gating_config()


@router.put("/gating", dependencies=[Depends(deps.require_perm("config"))])
def set_gating(body: dict):
    cfg = state.get_gating_config()
    state.set_gating_config(
        single_signal_floor=float(body.get("single_signal_floor", cfg["single_signal_floor"])),
        budget_window=int(body.get("budget_window", cfg["budget_window"])),
    )
    return state.get_gating_config()


def _mask(key: str) -> str:
    if not key:
        return ""
    return f"••••{key[-4:]}" if len(key) > 4 else "••••"


@router.get("/model")
def get_model():
    m = state.get_model_config()
    return {**m, "api_key": _mask(m["api_key"]), "deep_api_key": _mask(m["deep_api_key"])}


@router.put("/model", dependencies=[Depends(deps.require_perm("config"))])
def set_model(body: dict):
    m = state.get_model_config()
    # key 掩码或空 = 不覆盖；给新值才更新
    if body.get("api_key") and not str(body["api_key"]).startswith("••••"):
        m["api_key"] = body["api_key"]
    if body.get("deep_api_key") and not str(body["deep_api_key"]).startswith("••••"):
        m["deep_api_key"] = body["deep_api_key"]
    for k in ("base_url", "model", "deep_base_url", "deep_model", "temperature", "timeout"):
        if k in body and body[k] is not None:
            m[k] = body[k]
    m = state.set_model_config(m)
    return {**m, "api_key": _mask(m["api_key"]), "deep_api_key": _mask(m["deep_api_key"])}


@router.post("/model/test", dependencies=[Depends(deps.require_perm("config"))])
def test_model(body: dict):
    """测试模型连通性：用前端表单当前值发一条最小请求（key 掩码/空则回退已保存值）。"""
    saved = state.get_model_config()
    target = body.get("target", "system1")

    def eff(new_val, saved_field, env_name, default):
        return new_val or saved.get(saved_field) or os.environ.get(env_name, "").strip() or default

    def eff_key(new_key, saved_field):
        if new_key and not str(new_key).startswith("••••"):
            return new_key
        return saved.get(saved_field, "")

    if target == "system2":
        api_key = (eff_key(body.get("deep_api_key"), "deep_api_key")
                   or saved.get("api_key")
                   or os.environ.get("NEUROIMMUNE_DEEP_API_KEY", "").strip()
                   or os.environ.get("NEUROIMMUNE_API_KEY", "").strip())
        base_url = (eff(body.get("deep_base_url"), "deep_base_url", "NEUROIMMUNE_DEEP_BASE_URL", "")
                    or eff(body.get("base_url"), "base_url", "NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1"))
        model = eff(body.get("deep_model"), "deep_model", "NEUROIMMUNE_DEEP_MODEL", "deepseek-reasoner")
    else:
        api_key = (eff_key(body.get("api_key"), "api_key")
                   or os.environ.get("NEUROIMMUNE_API_KEY", "").strip())
        base_url = eff(body.get("base_url"), "base_url", "NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1")
        model = eff(body.get("model"), "model", "NEUROIMMUNE_MODEL", "deepseek-chat")

    if not api_key:
        return {"ok": False, "error": "未配置 API key（mock 模式无需测试）", "elapsed": 0}

    return llm.test_connection(base_url, api_key, model)


@router.get("/detection")
def get_detection():
    return state.get_detection_config()


@router.put("/detection", dependencies=[Depends(deps.require_perm("config"))])
def set_detection(body: dict):
    return state.set_detection_config(body)


@router.get("/ingest")
def get_ingest():
    ing = state.get_ingest_config()
    return {**ing, "api_token": _mask(ing["api_token"])}


@router.put("/ingest", dependencies=[Depends(deps.require_perm("config"))])
def set_ingest(body: dict):
    ing = state.get_ingest_config()
    if body.get("api_token") and not str(body["api_token"]).startswith("••••"):
        ing["api_token"] = body["api_token"]
    for k in ("syslog_bind", "syslog_port", "consolidate_interval", "retention_alert_days", "retention_case_days"):
        if k in body and body[k] is not None:
            ing[k] = body[k]
    ing = state.set_ingest_config(ing)
    return {**ing, "api_token": _mask(ing["api_token"])}


@router.get("/sources")
def get_sources():
    return state.get_sources_config()


@router.put("/sources", dependencies=[Depends(deps.require_perm("config"))])
def set_sources(body: dict):
    return state.set_sources_config(body)


@router.get("/assets")
def get_assets():
    """内部资产清单：[{role, value, criticality}]。"""
    return {"items": db.list_assets()}


@router.put("/assets", dependencies=[Depends(deps.require_perm("config"))])
def set_assets(body: dict):
    """整体替换资产清单。body: {items: [{role, value, criticality}]}。"""
    rows = (body or {}).get("items") or []
    return {"items": db.replace_assets(rows)}


@router.get("/sources/status")
def source_status():
    """接入现状：按来源映射配置列出已配置来源，附带告警数 / 最近入库时间。"""
    cfg = state.get_sources_config()
    configured = sorted({
        v for sec in ("facility", "hostname", "tag", "ip")
        for v in (cfg.get(sec) or {}).values() if v
    })
    stats = {s["source"]: s for s in db.get_source_stats()}
    empty = {"count": 0, "surfaced": 0, "suppressed": 0, "last_seen_ts": None}
    items = [{"source": name, **{**empty, **stats.get(name, {})}} for name in configured]
    return {"items": items}


@router.get("/memory", dependencies=[Depends(deps.require_perm("config"))])
def list_memory():
    return {"items": db.get_memory()}


@router.delete("/memory", dependencies=[Depends(deps.require_perm("config"))])
def clear_memory():
    db.clear_memory()
    return {"items": db.get_memory()}


@router.delete("/memory/{index}", dependencies=[Depends(deps.require_perm("config"))])
def delete_memory(index: int):
    if not db.delete_memory(index):
        raise HTTPException(404, "记忆不存在")
    return {"items": db.get_memory()}


@router.get("/feedback", dependencies=[Depends(deps.require_perm("config"))])
def list_feedback():
    return {"items": db.get_feedback()}


@router.delete("/feedback", dependencies=[Depends(deps.require_perm("config"))])
def clear_feedback():
    db.clear_feedback()
    return {"items": db.get_feedback()}


@router.delete("/feedback/{index}", dependencies=[Depends(deps.require_perm("config"))])
def delete_feedback(index: int):
    if not db.delete_feedback(index):
        raise HTTPException(404, "反馈不存在")
    return {"items": db.get_feedback()}


# ---- 来源解析配置（方案 C：LLM 生成规则 + 运行时确定性解析）----

GENERATE_PARSER_SYSTEM = (
    "你是日志解析配置生成器。给你一个安全设备的原始告警日志样本（可能多条、格式相同或不同），"
    "分析格式并生成解析配置 JSON，把告警解析成统一结构。\n"
    "支持两种解析类型：\n"
    "- dissect：定长字段，用 delimiter 分隔，按 fields 列表顺序一一映射字段名；\n"
    "- kv：key/value 对，field_split 分键值对、value_split 分键值。\n"
    "若日志带标准 syslog 头（如 'Jul 17 11:24:08 host tag:'），配置里加 \"strip_syslog\": true。\n"
    "输出一个 JSON 对象：\n"
    "{\n"
    "  \"strip_syslog\": true 或 false（可选，带 syslog 头才加）,\n"
    "  \"parsers\": [\n"
    "    {\n"
    "      \"match\": \"startswith:<首字段前缀>\",\n"
    "      \"type\": \"dissect 或 kv\",\n"
    "      \"delimiter\": \"...\"（dissect 用）,\n"
    "      \"fields\": [\"字段名\", ...]（dissect 用，顺序必须与样本一致）,\n"
    "      \"field_split\": \"...\", \"value_split\": \"...\"（kv 用）,\n"
    "      \"map\": {\n"
    "        \"time\": \"时间字段名\",\n"
    "        \"type\": \"告警类型字段名\",\n"
    "        \"asset\": \"受害/资产字段名（通常是目的 IP 或服务器 IP）\",\n"
    "        \"entities\": [[\"源IP字段\",\"ip\"],[\"目的IP字段\",\"ip\"],[\"文件hash字段\",\"hash\"],[\"域名字段\",\"domain\"]]\n"
    "      }\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "规则：fields 顺序必须与样本严格一致；entities 只放关键实体字段（源/目的 IP、文件 hash、域名），"
    "不要把版本号、端口、UA 当实体；时间字段可能是不带单位的 Unix 秒/毫秒或 ISO 字符串，原样填字段名即可。"
    "只输出 JSON，不要其他文字。"
)


@router.get("/parsers")
def get_parsers():
    return state.get_parsers_config()


@router.put("/parsers", dependencies=[Depends(deps.require_perm("config"))])
def set_parsers(body: dict):
    return state.set_parsers_config(body)


@router.post("/parsers/generate", dependencies=[Depends(deps.require_perm("config"))])
def generate_parsers(body: dict):
    """LLM 从样本生成解析配置（预览，不落盘）。body: {source, samples:[...]}。"""
    from amygdala import _extract_json
    source = (body or {}).get("source", "").strip()
    samples = (body or {}).get("samples", [])
    if not source or not samples:
        raise HTTPException(400, "source 和 samples 必填")
    prompt = (GENERATE_PARSER_SYSTEM + "\n\n来源名：" + source
              + "\n样本日志：\n" + json.dumps(samples, ensure_ascii=False, indent=2))
    raw = state.get_deep_client().analyze(prompt)
    try:
        cfg = _extract_json(raw)
    except ValueError as e:
        raise HTTPException(502, f"模型没输出合法 JSON：{e}")
    return {"config": cfg}


@router.post("/report/export")
def export_report(body: dict):
    """按筛选条件导出报告（docx / md / html）。body: {format, start, end, source, verdict, status}。"""
    body = body or {}
    fmt = body.get("format", "html")
    filters = {k: v for k, v in body.items() if k != "format" and v not in ("", None)}
    try:
        media, ext, content = report.export_report(filters, fmt)
    except ValueError as e:
        raise HTTPException(400, str(e))
    filename = f"neuroimmune-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/webhooks")
def list_webhooks():
    return {"items": webhook.load_webhooks()}


@router.post("/webhooks", dependencies=[Depends(deps.require_perm("config"))])
def add_webhook(body: dict):
    wbs = webhook.load_webhooks()
    wbs.append({
        "name": (body or {}).get("name", "webhook"),
        "url": (body or {}).get("url", ""),
        "token": (body or {}).get("token", ""),
        "trigger": (body or {}).get("trigger", "escalated"),
        "enabled": (body or {}).get("enabled", True),
        "fields": (body or {}).get("fields", webhook.ALL_FIELDS),
        "headers": (body or {}).get("headers", {}),
        "body": (body or {}).get("body", ""),
    })
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.put("/webhooks/{index}", dependencies=[Depends(deps.require_perm("config"))])
def update_webhook(index: int, body: dict):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    for k in ("name", "url", "token", "trigger", "enabled", "fields", "headers", "body"):
        if k in (body or {}):
            wbs[index][k] = body[k]
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.delete("/webhooks/{index}", dependencies=[Depends(deps.require_perm("config"))])
def delete_webhook(index: int):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    wbs.pop(index)
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.post("/webhooks/{index}/test", dependencies=[Depends(deps.require_perm("config"))])
def test_webhook(index: int):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    return {"ok": webhook.test_webhook(wbs[index])}


@router.put("/presets/{name}", dependencies=[Depends(deps.require_perm("config"))])
def update_preset(name: str, body: dict):
    if name not in config.PRESETS:
        raise HTTPException(404, f"未知档位 {name}")
    state.set_preset(
        name,
        suppress_below=float(body.get("suppress_below", 0.55)),
        escalate_above=float(body.get("escalate_above", 0.75)),
        budget=int(body.get("budget", 2)),
    )
    return state.get_all_presets()


@router.get("/info")
def info():
    import llm
    llm.load_dotenv()  # 保证 env fallback 可读
    m = state.get_model_config()
    ing = state.get_ingest_config()
    return {
        "syslog": {"bind": ing["syslog_bind"], "port": int(ing["syslog_port"])},
        "model": m["model"] or os.environ.get("NEUROIMMUNE_MODEL", "deepseek-chat"),
        "deep_model": m["deep_model"] or os.environ.get("NEUROIMMUNE_DEEP_MODEL", "deepseek-reasoner"),
        "mode": state.get_model_mode(),
    }
