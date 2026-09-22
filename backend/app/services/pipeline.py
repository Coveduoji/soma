"""管道服务——复用 prototype 的核心判断逻辑，把信号 → 案件/报告 → 落库。

核心判断（杏仁核 / 实体 / 图 / 系统2）一行不改，只把 main.py 的批处理逻辑
抽成可复用函数，产出落进 SQLite。
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import amygdala
import artifact
import assets as assets_mod
import blackboard
import config
import graph as graphmod
import innate
import system2
import tolerance

from app import crud as db
from app.services import state, webhook


# ---- 系统2 唤醒预算（滑动窗口计数）----
# prototype/receiver.py 是「每 window 秒收集候选、取前 budget 个唤醒」，但 Web 后端的
# process_signal 是持续流式（syslog + HTTP 上传），没有天然窗口。这里用滑动窗口计数：
# 最近 window 秒内，最多 budget 个「不同案件」唤醒系统2；同一案件随告警
# 增长（grew>=2）的重分析不计入新预算——它还是那一个案件，只是补全证据。进程内共享，重启归零。
# window / 单信号地板值都从 state.get_gating_config() 读，设置页可调。
_woken_cases: dict[int, float] = {}  # case_id -> 最近一次唤醒时间
_wake_lock = threading.Lock()

# 归案/建案/写库的全局串行锁：并发 worker 下，同一实体首现可能重复建案、
# get_or_create_artifact 可能撞 UNIQUE，必须串行化归案这一段（模型调用在锁外）。
_ingest_lock = threading.Lock()

# ---- 内部资产清单缓存 + 解析前置富化 ----
_assets_cache: list[dict] | None = None
_assets_cache_time = 0.0

# 风险模型归一化：标准枚举 → 0-1 数值
CRITICALITY_VAL = {"normal": 0.3, "important": 0.6, "critical": 1.0}
ATTACK_RESULT_VAL = {"blocked": 0.0, "failed": 0.0, "success": 0.7, "compromised": 1.0}
SEVERITY_VAL = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}

# 攻击结果 raw 兜底正则（来源没配解析规则时从原文猜）
_ATTACK_RESULT_GUESS = [
    (re.compile(r"已拦截|已阻断|已阻止|blocked|deny", re.IGNORECASE), "blocked"),
    (re.compile(r"失陷|入侵成功|已沦陷|compromised", re.IGNORECASE), "compromised"),
    (re.compile(r"成功|success", re.IGNORECASE), "success"),
    (re.compile(r"失败|failed|attempt", re.IGNORECASE), "failed"),
]


def _guess_attack_result(raw: str) -> str | None:
    for pat, val in _ATTACK_RESULT_GUESS:
        if pat.search(raw or ""):
            return val
    return None


def _get_assets() -> list[dict]:
    """读资产清单（进程内 TTL 缓存 10 秒；配置类数据低频改，改动最多 10 秒后生效）。"""
    global _assets_cache, _assets_cache_time
    now = time.time()
    if _assets_cache is None or now - _assets_cache_time > 10:
        _assets_cache = db.list_assets()
        _assets_cache_time = now
    return _assets_cache


def _enrich_signal(signal: dict) -> None:
    """解析前置富化：实体兜底抽取 + 资产匹配标注 + 风险分计算。raw 原样保留。"""
    if not signal.get("entities"):
        ents = artifact.extract_entities({"asset": signal.get("asset", ""), "raw": signal.get("raw", "")})
        signal["entities"] = [{"type": e.type, "value": e.value} for e in ents]
    assets = _get_assets()
    if assets:
        for ent in signal.get("entities", []):
            m = assets_mod.match_asset(ent.get("value", ""), assets)
            if m:
                ent["role"] = m["role"]
                ent["criticality"] = m["criticality"]

    # 攻击结果 raw 兜底（来源没配解析规则时，从原文猜）
    if not signal.get("attack_result"):
        guessed = _guess_attack_result(signal.get("raw", ""))
        if guessed:
            signal["attack_result"] = guessed

    # 风险分 = 资产价值 × 攻击得逞 × 攻击类型危害；缺失维度用保守默认并标记 risk_incomplete
    risk_incomplete = False
    crit_vals = [CRITICALITY_VAL.get(ent.get("criticality", "normal"), 0.3)
                 for ent in signal.get("entities", []) if ent.get("criticality")]
    criticality_val = max(crit_vals) if crit_vals else 0.3  # 无内部资产按「普通」算

    ar = signal.get("attack_result")
    if ar in ATTACK_RESULT_VAL:
        attack_val = ATTACK_RESULT_VAL[ar]
    else:
        attack_val = 1.0  # 保守：假设得逞
        risk_incomplete = True

    sv = signal.get("severity")
    if sv in SEVERITY_VAL:
        severity_val = SEVERITY_VAL[sv]
    else:
        severity_val = 0.5  # 中性：medium
        risk_incomplete = True

    signal["risk"] = round(criticality_val * attack_val * severity_val, 3)
    signal["risk_incomplete"] = risk_incomplete


def _within_budget(budget: int, window: int) -> bool:
    """当前是否还能唤醒系统2：窗口内已唤醒的不同案件数 < budget。"""
    cutoff = time.time() - window
    with _wake_lock:
        for cid in [c for c, t in _woken_cases.items() if t <= cutoff]:
            _woken_cases.pop(cid, None)
        return len(_woken_cases) < budget


def _record_wake(case_id: int) -> None:
    with _wake_lock:
        _woken_cases[case_id] = time.time()


# 同一案件随告警增长会触发多次重分析（grew>=2）。并发跑会竞态：早启动的（证据少）
# 可能后写完、覆盖晚启动的（证据全）。用 per-case 锁串行化：后启动的排队，最后写完的
# 是证据最全的那份报告。
_case_locks: dict[int, threading.Lock] = {}
_case_locks_guard = threading.Lock()


def _case_lock(case_id: int) -> threading.Lock:
    with _case_locks_guard:
        return _case_locks.setdefault(case_id, threading.Lock())


def _run_system2(case_id: int, events, deep_client, knowledge) -> None:
    """后台跑系统2，per-case 串行，不阻塞入库。"""
    with _case_lock(case_id):
        db.insert_report(case_id, system2.deep_analyze_chain(events, deep_client, knowledge))
    webhook.notify("escalated", case_id)  # 深析报告就绪后外发


def _alert_to_event(a: dict) -> blackboard.Event:
    return blackboard.Event(
        time=a["time"], source=a["source"], asset=a["asset"], etype=a["type"],
        confidence=a["confidence"], raw=a["raw"], reason=a["reason"], innate=bool(a["innate"]),
    )


def _retrieve_knowledge(entity_values: list[str], limit: int = 5) -> list[str]:
    """记忆 RAG：按实体值检索过去的误报经验和历史记忆。"""
    knowledge = []
    for rec in db.get_feedback():
        vals = {e[0] for e in rec.get("entities", []) if isinstance(e, list) and e}
        if any(v in vals for v in entity_values):
            label = "真阳性经验" if rec.get("type") == "true_positive" else "误报经验"
            knowledge.append(f"{label}（{rec.get('case_uid', '')[:8]}）：{rec.get('reason', '')}")
    for rec in db.get_memory():
        text = rec.get("summary", "")
        if text and any(v in text for v in entity_values):
            knowledge.append(f"历史记忆：{text}")
    return knowledge[-limit:]


def _alert_event(a: dict, artifacts: list[dict]) -> blackboard.Event:
    """告警 dict + 实体 → 黑板上事件（含 entities，供系统2 研判）。"""
    return blackboard.Event(
        time=a["time"], source=a["source"], asset=a["asset"], etype=a["type"],
        confidence=a["confidence"], raw=a["raw"], reason=a["reason"], innate=bool(a["innate"]),
        entities=[{"type": x["type"], "value": x["value"]} for x in artifacts],
    )


def analyze_case(case_id: int) -> dict:
    """主动研判一个案件：同步跑系统2 深想，覆盖/刷新案件报告。"""
    d = state.get_detection_config()
    deep_client = state.get_deep_client()
    alerts = db.get_case_alerts(case_id)
    events: list[blackboard.Event] = []
    entity_values: list[str] = []
    for a in alerts:
        arts = db.get_alert_artifacts(a["id"])
        entity_values.extend(x["value"] for x in arts)
        events.append(_alert_event(a, arts))
    knowledge = _retrieve_knowledge(entity_values, d["rag_limit"])
    with _case_lock(case_id):
        report = system2.deep_analyze_chain(events, deep_client, knowledge)
        db.insert_report(case_id, report)
    return report


def analyze_alert(alert_id: int) -> dict:
    """主动研判单条告警：同步跑系统2 深想（单信号），不落库。"""
    d = state.get_detection_config()
    a = db.get_alert(alert_id)
    arts = db.get_alert_artifacts(alert_id)
    event = _alert_event(a, arts)
    knowledge = _retrieve_knowledge([x["value"] for x in arts], d["rag_limit"])
    return system2.deep_analyze_chain([event], state.get_deep_client(), knowledge)


def process_signal(signal: dict, knob_name: str | None = None) -> dict:
    """增量处理一条信号：过管道 → 按实体归入/合并案件 → 首次顶出才系统2。

    这是 24h 流式入库的核心：不重置、不跑全量，每条信号用 correlation_uid 的实体
    反查已有案件，归入或合并，案件强度动态累加。knob_name 为空时用全局旋钮。
    """
    knob = state.get_knob(knob_name or state.get_knob_name())
    d = state.get_detection_config()
    gating = state.get_gating_config()
    client = state.get_client()
    deep_client = state.get_deep_client()
    tol = tolerance.load_tolerance()
    rules = innate.load_rules()
    ttl = d["tolerance_ttl_days"] * 86400  # 白名单 TTL（秒），0=永久

    def _suppress(why: str, confidence=None) -> dict:
        db.insert_suppressed_alert({**signal, "confidence": confidence}, why)
        return {"status": "suppressed", "why": why}

    # 解析前置富化：实体兜底抽取 + 资产匹配标注（raw 原样保留）
    _enrich_signal(signal)

    # 黑名单优先于白名单：宁可多报不可漏（签名若同时命中黑白名单，走秒拦而非静默）。
    if innate.match(signal, rules):
        e = blackboard.Event(
            time=signal["time"], source=signal["source"], asset=signal["asset"], etype=signal["type"],
            confidence=d["innate_conf"], raw=signal["raw"], reason="固有免疫秒拦：已知攻击家族", innate=True,
            entities=signal.get("entities", []),
        )
    elif tolerance.is_tolerated(signal, tol, ttl):
        return _suppress("免疫耐受：已知好，白名单降级")
    else:
        v = amygdala.judge_signal(signal, client)
        # 频率降级：时间窗外历史同类型告警极多 → 很可能业务误报，降级并写记忆
        freq = state.get_freq_config()
        hist = db.count_historical_alerts(signal["asset"], signal["type"], freq["window"])
        freq_demoted = False
        if hist >= freq["threshold"]:
            v = amygdala.Verdict(
                v.suspicious, round(v.confidence * freq["demote"], 2),
                f"{v.reason}（历史同类型告警 {hist} 次，疑似业务误报）",
            )
            freq_demoted = True
            db.append_feedback({
                "type": "frequency_false_positive",
                "asset": signal["asset"], "signal_type": signal["type"],
                "count": hist, "time": datetime.now().isoformat(),
            })
        # 出口 IP 降噪：任一 IP 实体是我们的出口 IP → 内部出网，温和降噪
        # （不误降 C2 回连——真正的可疑交给二期风险模型结合攻击结果细化）
        egress_demoted = False
        if any(ent.get("role") == "出口IP" for ent in signal.get("entities", [])):
            v = amygdala.Verdict(
                v.suspicious, round(v.confidence * 0.85, 2),
                f"{v.reason}（源为出口 IP，内部出网）",
            )
            db.insert_audit("egress_demote", f"signal {signal.get('asset', '')}",
                            json.dumps({"confidence": v.confidence}, ensure_ascii=False))
            egress_demoted = True
        if v.confidence < knob.suppress_below:
            why = (f"频率降级：历史同类型告警 {hist} 次，疑似业务误报"
                   if freq_demoted else
                   f"出口 IP 降噪：源为出口 IP（内部出网），降噪后 {v.confidence:.2f} < {knob.suppress_below}"
                   if egress_demoted else
                   f"杏仁核低置信度（{v.confidence:.2f} < {knob.suppress_below}）")
            return _suppress(why, confidence=v.confidence)
        e = blackboard.Event(
            time=signal["time"], source=signal["source"], asset=signal["asset"], etype=signal["type"],
            confidence=v.confidence, raw=signal["raw"], reason=v.reason,
            entities=signal.get("entities", []),
        )

    # 实体：富化已抽出并标注，直接复用
    ents = [artifact.Entity(x["type"], x["value"]) for x in signal.get("entities", [])]

    # 归案 + 写库在全局锁内串行（并发 worker 下避免重复建案/撞 UNIQUE）。
    # 模型调用（amygdala.judge）在锁外，锁内只有毫秒级 DB 读写，不构成瓶颈。
    with _ingest_lock:
        # 归案：任一实体命中的已有案件
        case_ids: set[int] = set()
        for ent in ents:
            for c in db.cases_for_entity(ent.type, ent.value):
                case_ids.add(c["id"])

        if len(case_ids) > 1:
            keep = min(case_ids)
            for cid in sorted(case_ids - {keep}):
                db.merge_case(cid, keep)
            case_id = keep
        elif len(case_ids) == 1:
            case_id = case_ids.pop()
        else:
            uid = graphmod.component_id(ents)
            title = "、".join(x.value for x in ents[:3]) or "未命名案件"
            case_id = db.insert_case(
                correlation_uid=uid, title=title, strength=0.0,
                entity_summary=json.dumps([{"type": x.type, "value": x.value} for x in ents], ensure_ascii=False),
            )

        alert_id = db.insert_alert(case_id, e)
        for ent in ents:
            db.link_alert_artifact(alert_id, db.get_or_create_artifact(ent.type, ent.value))

        # 更新案件强度 + 风险分（风险 = 案件所有告警风险的最大值）
        alerts = db.get_case_alerts(case_id)
        strength = max(a["confidence"] for a in alerts) + min(d["chain_cap"], d["chain_bonus"] * (len(alerts) - 1))
        db.update_case_strength(case_id, round(strength, 3))
        case_risk = max(signal.get("risk", 0), db.get_case(case_id).get("risk", 0) or 0)
        db.update_case_risk(case_id, round(case_risk, 3))

    # 顶出决策：风险分越过风险阈值才考虑唤醒系统2，但要过两重门——
    #   ① 单信号门槛：单信号案件默认不醒（除非 conf >= 地板值），要等拼链或确凿单点 IOC；
    #   ② 预算门：滑动窗口内最多 knob.budget 个不同案件唤醒。
    # 被门拦下的也写审计——「抑制不是静默，全程可审计」。
    if case_risk >= d.get("risk_threshold", 0.3):
        max_conf = max(a["confidence"] for a in alerts)
        worthy = len(alerts) >= 2 or max_conf >= gating["single_signal_floor"]
        report_exists = db.get_case_report(case_id) is not None
        grew = len(alerts) - (db.get_case(case_id).get("reported_at_alerts") or 0) >= d["grew"]
        if worthy and (not report_exists or grew):
            if _within_budget(knob.budget, gating["budget_window"]):
                _record_wake(case_id)
                events = [_alert_to_event(a) for a in alerts]
                knowledge = _retrieve_knowledge([x.value for x in ents], d["rag_limit"])
                db.set_case_reported_alerts(case_id, len(alerts))
                threading.Thread(
                    target=_run_system2, args=(case_id, events, deep_client, knowledge),
                    daemon=True,
                ).start()
            else:
                db.insert_audit("budget_blocked", f"case {case_id}",
                                json.dumps({"risk": case_risk, "alerts": len(alerts),
                                            "budget": knob.budget}, ensure_ascii=False))
        elif not worthy:
            db.insert_audit("single_signal_skipped", f"case {case_id}",
                            json.dumps({"max_conf": max_conf, "alerts": len(alerts),
                                        "floor": gating["single_signal_floor"]}, ensure_ascii=False))

    return {"status": "ingested", "case_id": case_id, "strength": round(strength, 3),
            "risk": case_risk, "alerts": len(alerts)}


def restore_signal(signal: dict) -> dict:
    """分析师放回一条被误压的信号：强制上板、归入案件、触发系统2 深想。"""
    d = state.get_detection_config()
    deep_client = state.get_deep_client()
    e = blackboard.Event(
        time=signal.get("time", ""), source=signal.get("source", ""), asset=signal.get("asset", ""),
        etype=signal.get("type", ""), confidence=d["restore_conf"], raw=signal.get("raw", ""),
        reason="分析师放回：被误压的信号",
    )
    ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})
    # 与流式 process_signal 共享同一把归案锁，避免放回动作与并发入库竞态。
    # 归案改用实体反查（对齐 process_signal），不再用 correlation_uid 精确匹配：
    # 放回信号若共享已有案件的实体，会正确并回原链，而不是拆成新案。
    with _ingest_lock:
        case_ids: set[int] = set()
        for ent in ents:
            for c in db.cases_for_entity(ent.type, ent.value):
                case_ids.add(c["id"])

        if len(case_ids) > 1:
            keep = min(case_ids)
            for cid in sorted(case_ids - {keep}):
                db.merge_case(cid, keep)
            case_id = keep
        elif len(case_ids) == 1:
            case_id = case_ids.pop()
        else:
            uid = graphmod.component_id(ents)
            title = "、".join(f"{x.value}" for x in ents[:3]) or "放回信号"
            case_id = db.insert_case(
                correlation_uid=uid, title=title, strength=d["restore_conf"],
                entity_summary=json.dumps([{"type": x.type, "value": x.value} for x in ents], ensure_ascii=False),
            )

        alert_id = db.insert_alert(case_id, e)
        for ent in ents:
            db.link_alert_artifact(alert_id, db.get_or_create_artifact(ent.type, ent.value))

        # 更新案件强度（放回信号以 restore_conf 抬高所在案件，同 process_signal）
        alerts = db.get_case_alerts(case_id)
        strength = max(a["confidence"] for a in alerts) + min(d["chain_cap"], d["chain_bonus"] * (len(alerts) - 1))
        db.update_case_strength(case_id, round(strength, 3))
        uid = db.get_case(case_id)["correlation_uid"]

    # 后台跑系统2，放回立即返回、不阻塞，带记忆 RAG
    knowledge = _retrieve_knowledge([x.value for x in ents], d["rag_limit"])
    threading.Thread(
        target=lambda: db.insert_report(case_id, system2.deep_analyze_chain([e], deep_client, knowledge)),
        daemon=True,
    ).start()
    return {"case_id": case_id, "correlation_uid": uid}
