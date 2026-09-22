"""复杂查询与聚合——复刻旧 db.py 的 SQL，返回 dict 与旧版完全一致。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from sqlalchemy import select, func, text, or_, cast, String, case
from sqlalchemy.orm import aliased

from app.db.session import SessionLocal
from app.models import User, Case, Alert, Artifact, AlertArtifact, Report, AuditLog

from app.crud import _alert_row, _case_row


def _case_filter(status=None, verdict=None, severity=None, pending=False, query=None, risk=None):
    conds = []
    if status:
        conds.append(Case.status == status)
    if pending:
        conds.append(Case.status.in_(["New", "In Progress", "On Hold"]))
    if verdict:
        conds.append(Case.verdict == verdict)
    if severity:
        conds.append(Case.severity == severity)
    if risk == "high":
        conds.append(Case.risk >= 0.3)
    elif risk == "mid":
        conds.append(Case.risk >= 0.1)
        conds.append(Case.risk < 0.3)
    elif risk == "low":
        conds.append(Case.risk < 0.1)
    if query:
        like = f"%{query}%"
        conds.append(or_(
            Case.correlation_uid.like(like),
            Case.title.like(like),
            cast(Case.entity_summary, String).like(like),
        ))
    return conds


def list_cases(status=None, verdict=None, severity=None, pending=False, query=None,
               risk=None, limit=50, offset=0) -> list[dict]:
    with SessionLocal() as s:
        conds = _case_filter(status, verdict, severity, pending, query, risk)
        q = select(Case).where(*conds).order_by(Case.risk.desc(), Case.id.desc()).limit(limit).offset(offset)
        return [_case_row(c) for c in s.execute(q).scalars().all()]


def count_cases(status=None, verdict=None, severity=None, pending=False, query=None, risk=None) -> int:
    with SessionLocal() as s:
        conds = _case_filter(status, verdict, severity, pending, query, risk)
        q = select(func.count()).select_from(Case).where(*conds)
        return s.execute(q).scalar_one()


def get_case(case_id: int) -> dict | None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        return _case_row(c) if c else None


def get_case_by_uid(uid: str) -> dict | None:
    with SessionLocal() as s:
        c = s.execute(select(Case).where(Case.correlation_uid == uid)).scalar_one_or_none()
        return _case_row(c) if c else None


def get_case_alerts(case_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.execute(select(Alert).where(Alert.case_id == case_id).order_by(Alert.id)).scalars().all()
        return [_alert_row(a) for a in rows]


def get_alert_artifacts(alert_id: int) -> list[dict]:
    with SessionLocal() as s:
        q = (select(Artifact.type, Artifact.value)
             .join(AlertArtifact, AlertArtifact.artifact_id == Artifact.id)
             .where(AlertArtifact.alert_id == alert_id))
        return [{"type": r[0], "value": r[1]} for r in s.execute(q).all()]


def get_case_report(case_id: int) -> dict | None:
    with SessionLocal() as s:
        r = s.execute(select(Report).where(Report.case_id == case_id)).scalar_one_or_none()
        if not r:
            return None
        return {
            "id": r.id, "case_id": r.case_id, "verdict": r.verdict, "confidence": r.confidence,
            "digest": r.digest, "evidence": r.evidence_json or [], "iocs": r.iocs_json or [],
            "unknowns": r.unknowns_json or [], "remediations": r.remediations_json or [],
            "attack_chain": r.attack_chain_json or [],
        }


def cases_for_entity(type_: str, value: str) -> list[dict]:
    with SessionLocal() as s:
        q = (select(Case).distinct()
             .join(Alert, Alert.case_id == Case.id)
             .join(AlertArtifact, AlertArtifact.alert_id == Alert.id)
             .join(Artifact, Artifact.id == AlertArtifact.artifact_id)
             .where(Artifact.type == type_, Artifact.value == value)
             .order_by(Case.risk.desc()))
        return [_case_row(c) for c in s.execute(q).scalars().all()]


def get_audit(audit_id: int) -> dict | None:
    with SessionLocal() as s:
        a = s.get(AuditLog, audit_id)
        return _audit_row(a) if a else None


def _audit_row(a: AuditLog) -> dict:
    return {"id": a.id, "action": a.action, "entity": a.entity, "changes": a.changes, "created_at": a.created_at}


def list_audit(action: str | None = None) -> list[dict]:
    with SessionLocal() as s:
        q = select(AuditLog).order_by(AuditLog.id.desc())
        if action:
            q = q.where(AuditLog.action == action)
        return [_audit_row(a) for a in s.execute(q).scalars().all()]


def get_all_artifacts() -> list[dict]:
    with SessionLocal() as s:
        return [{"id": a.id, "type": a.type, "value": a.value} for a in s.execute(select(Artifact)).scalars().all()]


def get_all_alert_artifacts() -> list[dict]:
    with SessionLocal() as s:
        q = (select(AlertArtifact.alert_id, Alert.case_id, AlertArtifact.artifact_id)
             .join(Alert, Alert.id == AlertArtifact.alert_id))
        return [{"alert_id": r[0], "case_id": r[1], "artifact_id": r[2]} for r in s.execute(q).all()]


def get_case_uid_map() -> dict[int, str]:
    with SessionLocal() as s:
        rows = s.execute(select(Case.id, Case.correlation_uid)).all()
        return {r[0]: r[1] for r in rows}


def get_distinct_sources() -> list[str]:
    with SessionLocal() as s:
        q = select(Alert.source).where(Alert.source != "").distinct()
        return [r[0] for r in s.execute(q).all()]


def get_source_stats() -> list[dict]:
    with SessionLocal() as s:
        q = (select(
            Alert.source,
            func.count().label("count"),
            func.coalesce(func.sum(case((Alert.suppressed == 0, 1), else_=0)), 0).label("surfaced"),
            func.coalesce(func.sum(case((Alert.suppressed == 1, 1), else_=0)), 0).label("suppressed"),
            func.max(func.strftime("%s", Alert.created_at)).label("last_seen_ts"),
        ).where(Alert.source != "").group_by(Alert.source))
        out = []
        for r in s.execute(q).all():
            out.append({
                "source": r[0], "count": r[1], "surfaced": r[2], "suppressed": r[3],
                "last_seen_ts": int(r[4]) if r[4] else None,
            })
        return out


def _alert_where(source: str | None):
    return ([Alert.source == source] if source else [])


def _order_by(sort: str):
    return Alert.confidence.desc() if sort == "confidence" else Alert.id.desc()


def get_alerts_for_entity(type_, value, source=None, sort="time", limit=200, offset=0):
    with SessionLocal() as s:
        conds = [Artifact.type == type_, Artifact.value == value] + _alert_where(source)
        q = (select(Alert, Case.correlation_uid, Case.id)
             .join(AlertArtifact, AlertArtifact.alert_id == Alert.id)
             .join(Artifact, Artifact.id == AlertArtifact.artifact_id)
             .join(Case, Case.id == Alert.case_id)
             .where(*conds).distinct()
             .order_by(_order_by(sort)).limit(limit).offset(offset))
        out = []
        for r in s.execute(q).all():
            d = _alert_row(r[0])
            d["case_uid"] = r[1]
            d["case_id"] = r[2]
            out.append(d)
        return out


def count_alerts_for_entity(type_, value, source=None) -> int:
    with SessionLocal() as s:
        conds = [Artifact.type == type_, Artifact.value == value] + _alert_where(source)
        q = (select(func.count(func.distinct(Alert.id)))
             .select_from(Alert)
             .join(AlertArtifact, AlertArtifact.alert_id == Alert.id)
             .join(Artifact, Artifact.id == AlertArtifact.artifact_id)
             .where(*conds))
        return s.execute(q).scalar_one()


def get_alerts_for_entity_pair(type1, value1, type2, value2, source=None, sort="time", limit=200, offset=0):
    with SessionLocal() as s:
        aa1 = aliased(AlertArtifact)
        aa2 = aliased(AlertArtifact)
        a1 = aliased(Artifact)
        a2 = aliased(Artifact)
        conds = [a1.type == type1, a1.value == value1, a2.type == type2, a2.value == value2] + _alert_where(source)
        q = (select(Alert, Case.correlation_uid, Case.id)
             .join(aa1, aa1.alert_id == Alert.id)
             .join(a1, a1.id == aa1.artifact_id)
             .join(aa2, aa2.alert_id == Alert.id)
             .join(a2, a2.id == aa2.artifact_id)
             .join(Case, Case.id == Alert.case_id)
             .where(*conds).distinct()
             .order_by(_order_by(sort)).limit(limit).offset(offset))
        out = []
        for r in s.execute(q).all():
            d = _alert_row(r[0])
            d["case_uid"] = r[1]
            d["case_id"] = r[2]
            out.append(d)
        return out


def count_alerts_for_entity_pair(type1, value1, type2, value2, source=None) -> int:
    with SessionLocal() as s:
        aa1 = aliased(AlertArtifact)
        aa2 = aliased(AlertArtifact)
        a1 = aliased(Artifact)
        a2 = aliased(Artifact)
        conds = [a1.type == type1, a1.value == value1, a2.type == type2, a2.value == value2] + _alert_where(source)
        q = (select(func.count(func.distinct(Alert.id)))
             .select_from(Alert)
             .join(aa1, aa1.alert_id == Alert.id)
             .join(a1, a1.id == aa1.artifact_id)
             .join(aa2, aa2.alert_id == Alert.id)
             .join(a2, a2.id == aa2.artifact_id)
             .where(*conds))
        return s.execute(q).scalar_one()


def patch_case(case_id: int, changes: dict) -> None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        if not c:
            return
        for k, v in changes.items():
            setattr(c, k, v)
        s.commit()


def update_case_strength(case_id: int, strength: float) -> None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        if c:
            c.strength = strength
            s.commit()


def update_case_risk(case_id: int, risk: float, incomplete: bool = False) -> None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        if c:
            c.risk = risk
            # 一旦标记为「风险信息不全」就保持（案内曾出现过保守默认），后续完整告警不撤销
            c.risk_incomplete = bool(c.risk_incomplete or incomplete)
            s.commit()


def merge_case(from_id: int, to_id: int) -> None:
    with SessionLocal() as s:
        s.execute(text("UPDATE alerts SET case_id=:to WHERE case_id=:frm"), {"to": to_id, "frm": from_id})
        s.execute(text("DELETE FROM cases WHERE id=:id"), {"id": from_id})
        s.execute(text("DELETE FROM reports WHERE case_id=:id"), {"id": from_id})
        s.commit()


def counts() -> dict:
    with SessionLocal() as s:
        def n(q):
            return s.execute(q).scalar_one()
        return {
            "alerts": n(select(func.count()).select_from(Alert)),
            "surfaced": n(select(func.count()).select_from(Alert).where(Alert.suppressed == 0)),
            "suppressed": n(select(func.count()).select_from(Alert).where(Alert.suppressed == 1)),
            "artifacts": n(select(func.count()).select_from(Artifact)),
            "cases": n(select(func.count()).select_from(Case)),
            "reports": n(select(func.count()).select_from(Report)),
            "attack_chains": n(select(func.count()).select_from(Report).where(func.cast(Report.attack_chain_json, String) != "[]")),
            "audit": n(select(func.count()).select_from(AuditLog)),
        }


def set_alert_verdict(alert_id: int, verdict: str) -> None:
    with SessionLocal() as s:
        a = s.get(Alert, alert_id)
        if a:
            a.verdict = verdict
            s.commit()


def _all_alert_filter(source=None, suppressed=None, q=None):
    conds = []
    if source:
        conds.append(Alert.source == source)
    if suppressed == "1":
        conds.append(Alert.suppressed == 1)
    elif suppressed == "0":
        conds.append(Alert.suppressed == 0)
    if q:
        like = f"%{q}%"
        conds.append(or_(Alert.raw.like(like), Alert.asset.like(like), Alert.type.like(like)))
    return conds


def list_all_alerts(source=None, suppressed=None, q=None, sort="time", limit=50, offset=0):
    with SessionLocal() as s:
        conds = _all_alert_filter(source, suppressed, q)
        qq = (select(Alert, Case.correlation_uid)
              .outerjoin(Case, Case.id == Alert.case_id)
              .where(*conds).order_by(_order_by(sort)).limit(limit).offset(offset))
        out = []
        for r in s.execute(qq).all():
            d = _alert_row(r[0])
            d["case_uid"] = r[1]
            out.append(d)
        return out


def count_all_alerts(source=None, suppressed=None, q=None) -> int:
    with SessionLocal() as s:
        conds = _all_alert_filter(source, suppressed, q)
        return s.execute(select(func.count()).select_from(Alert).where(*conds)).scalar_one()


def list_alerts_report(start=None, end=None, source=None, limit=100000):
    with SessionLocal() as s:
        conds = []
        if start:
            conds.append(Alert.created_at >= start)
        if end:
            conds.append(Alert.created_at <= end)
        if source:
            conds.append(Alert.source == source)
        qq = (select(Alert, Case.correlation_uid)
              .outerjoin(Case, Case.id == Alert.case_id)
              .where(*conds).order_by(Alert.id.desc()).limit(limit))
        out = []
        for r in s.execute(qq).all():
            d = _alert_row(r[0])
            d["case_uid"] = r[1]
            out.append(d)
        return out


def set_case_reported_alerts(case_id: int, count: int) -> None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        if c:
            c.reported_at_alerts = count
            s.commit()


def _ts_to_dt(ts: int | None) -> str | None:
    """unix 秒 → UTC 'YYYY-MM-DD HH:MM:SS'（与 Alert.created_at 存储格式一致）。"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _time_conds(start_ts: int | None, end_ts: int | None) -> list:
    """按时间范围生成 created_at 过滤条件。"""
    conds = [Alert.created_at != ""]
    if start_ts is not None:
        conds.append(Alert.created_at >= _ts_to_dt(start_ts))
    if end_ts is not None:
        conds.append(Alert.created_at <= _ts_to_dt(end_ts))
    return conds


def alert_trend(start_ts: int, end_ts: int) -> list[dict]:
    bucket = max(60, (end_ts - start_ts) // 30)
    with SessionLocal() as s:
        q = (select(func.strftime("%s", Alert.created_at), Alert.suppressed)
             .where(*_time_conds(start_ts, end_ts)))
        rows = s.execute(q).all()

    agg: dict[int, dict] = {}
    for t, suppressed in rows:
        b = int(t) // bucket * bucket
        d = agg.setdefault(b, {"total": 0, "surfaced": 0})
        d["total"] += 1
        if not suppressed:
            d["surfaced"] += 1

    start_bucket = start_ts // bucket * bucket
    nb = (end_ts - start_ts) // bucket + 1
    return [{"t": start_bucket + i * bucket,
             **agg.get(start_bucket + i * bucket, {"total": 0, "surfaced": 0})}
            for i in range(nb)]


def confidence_calibration(source: str | None = None, bins: int = 10,
                           start_ts: int | None = None, end_ts: int | None = None) -> list[dict]:
    """置信度校准：上板告警按置信度分桶，统计各桶告警数 + 被标注真阳/误报数，算实际准确率。"""
    conds = [Alert.suppressed == 0]
    if source:
        conds.append(Alert.source == source)
    if start_ts is not None:
        conds.append(Alert.created_at >= _ts_to_dt(start_ts))
    if end_ts is not None:
        conds.append(Alert.created_at <= _ts_to_dt(end_ts))
    with SessionLocal() as s:
        rows = s.execute(select(Alert.confidence, Alert.verdict).where(*conds)).all()

    buckets = [{"lo": i / bins, "hi": (i + 1) / bins, "label": f"{i / bins:.1f}-{(i + 1) / bins:.1f}",
                "count": 0, "tp": 0, "fp": 0, "tp_rate": None} for i in range(bins)]
    for conf, verdict in rows:
        if conf is None:
            continue
        idx = min(int(conf * bins), bins - 1)
        buckets[idx]["count"] += 1
        if verdict == "True Positive":
            buckets[idx]["tp"] += 1
        elif verdict == "False Positive":
            buckets[idx]["fp"] += 1
    for b in buckets:
        labeled = b["tp"] + b["fp"]
        if labeled:
            b["tp_rate"] = round(b["tp"] / labeled, 3)
    return buckets


def device_traffic(start_ts: int, end_ts: int) -> list[dict]:
    """按设备（来源）的告警流量：返回扁平 [{t, source, count}]，供多序列折线。"""
    bucket = max(60, (end_ts - start_ts) // 30)
    with SessionLocal() as s:
        q = (select(Alert.source, func.strftime("%s", Alert.created_at))
             .where(*_time_conds(start_ts, end_ts)))
        rows = s.execute(q).all()

    agg: dict[tuple[str, int], int] = {}
    for source, t in rows:
        b = int(t) // bucket * bucket
        agg[(source, b)] = agg.get((source, b), 0) + 1
    return [{"t": b, "source": src, "count": n}
            for (src, b), n in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1]))]


def device_classification(source: str | None = None,
                          start_ts: int | None = None, end_ts: int | None = None) -> list[dict]:
    """某设备（或全部）的告警按类型分类计数。"""
    conds = _time_conds(start_ts, end_ts)
    if source:
        conds.append(Alert.source == source)
    with SessionLocal() as s:
        q = (select(Alert.type, func.count())
             .where(*conds).group_by(Alert.type).order_by(func.count().desc()))
        return [{"type": t, "count": n} for t, n in s.execute(q).all()]


CASE_TRANSITIONS = {
    "New": {"In Progress", "On Hold", "Closed"},
    "In Progress": {"On Hold", "Resolved", "Closed"},
    "On Hold": {"In Progress", "Resolved", "Closed"},
    "Resolved": {"In Progress", "Closed"},
    "Closed": {"In Progress"},
}


def is_valid_transition(current: str, new: str) -> bool:
    return current == new or new in CASE_TRANSITIONS.get(current, set())


# ---- 保留策略 ----

def alerts_older_than(cutoff: str) -> list[dict]:
    with SessionLocal() as s:
        rows = s.execute(select(Alert).where(Alert.created_at < cutoff).order_by(Alert.created_at)).scalars().all()
        return [_alert_row(a) for a in rows]


def delete_alerts_older_than(cutoff: str) -> int:
    with SessionLocal() as s:
        ids = [r[0] for r in s.execute(select(Alert.id).where(Alert.created_at < cutoff)).all()]
        if ids:
            s.execute(text("DELETE FROM alert_artifacts WHERE alert_id IN (SELECT id FROM alerts WHERE created_at < :c)"), {"c": cutoff})
        n = s.execute(text("DELETE FROM alerts WHERE created_at < :c"), {"c": cutoff}).rowcount
        s.commit()
        return n


def delete_orphan_artifacts() -> int:
    with SessionLocal() as s:
        n = s.execute(text(
            "DELETE FROM artifacts WHERE id NOT IN (SELECT DISTINCT artifact_id FROM alert_artifacts)"
        )).rowcount
        s.commit()
        return n


def delete_cases_older_than(cutoff: str) -> int:
    with SessionLocal() as s:
        s.execute(text("DELETE FROM reports WHERE case_id IN (SELECT id FROM cases WHERE created_at < :c)"), {"c": cutoff})
        n = s.execute(text("DELETE FROM cases WHERE created_at < :c"), {"c": cutoff}).rowcount
        s.commit()
        return n
