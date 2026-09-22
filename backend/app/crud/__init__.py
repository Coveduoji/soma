"""数据访问层——把旧 db.py 的手写 sqlite3 迁移到 SQLAlchemy，返回 dict 与旧版完全一致。

JSON 列（permissions / entity_summary / *_json）由 SQLAlchemy JSON 类型自动序列化，
因此这里直接返回 Python list/dict，无需 json.loads。为兼容旧调用（pipeline 仍传
JSON 字符串），写入处用 _as_list 兜底。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import (User, Case, Alert, Artifact, AlertArtifact, Report, AuditLog, Asset)
from app.core.paths import FEEDBACK_PATH, MEMORY_PATH


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return json.loads(v or "[]")
    return v


# ---- 序列化（与旧 db.py 的 _user_row / _case_row 对齐）----

def _user_row(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "password_hash": u.password_hash,
        "role": u.role, "permissions": u.permissions or [], "created_at": u.created_at,
    }


def _case_row(c: Case) -> dict:
    return {
        "id": c.id, "correlation_uid": c.correlation_uid, "title": c.title,
        "strength": c.strength, "status": c.status, "verdict": c.verdict,
        "severity": c.severity, "risk": c.risk, "risk_incomplete": c.risk_incomplete,
        "entities": c.entity_summary or [],
        "disposition_note": c.disposition_note, "reported_at_alerts": c.reported_at_alerts,
        "created_at": c.created_at,
    }


def _alert_row(a: Alert) -> dict:
    return {
        "id": a.id, "case_id": a.case_id, "time": a.time, "source": a.source,
        "asset": a.asset, "type": a.type, "raw": a.raw, "confidence": a.confidence,
        "reason": a.reason, "innate": a.innate, "label": a.label, "suppressed": a.suppressed,
        "why": a.why, "verdict": a.verdict, "created_at": a.created_at,
    }


# ---- 用户 ----

def create_user(username: str, password_hash: str, role: str = "user",
                permissions: list[str] | None = None) -> int:
    with SessionLocal() as s:
        u = User(username=username, password_hash=password_hash, role=role,
                 permissions=permissions or [])
        s.add(u)
        s.commit()
        return u.id


def get_user(user_id: int) -> dict | None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        return _user_row(u) if u else None


def get_user_by_username(username: str) -> dict | None:
    with SessionLocal() as s:
        u = s.execute(select(User).where(User.username == username)).scalar_one_or_none()
        return _user_row(u) if u else None


def list_users() -> list[dict]:
    with SessionLocal() as s:
        rows = s.execute(select(User).order_by(User.id)).scalars().all()
        return [_user_row(u) for u in rows]


def delete_user(user_id: int) -> None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            s.delete(u)
            s.commit()


def update_user_password(user_id: int, password_hash: str) -> None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            u.password_hash = password_hash
            s.commit()


def update_user(user_id: int, changes: dict) -> None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return
        for k, v in changes.items():
            setattr(u, k, _as_list(v) if k == "permissions" else v)
        s.commit()


def count_admins() -> int:
    with SessionLocal() as s:
        return s.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar_one()


# ---- 反馈 / 记忆（JSONL 文件，保持与旧版一致）----

def append_feedback(record: dict) -> None:
    p = FEEDBACK_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _rewrite_jsonl(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def get_feedback() -> list[dict]:
    return _read_jsonl(FEEDBACK_PATH)


def get_memory() -> list[dict]:
    return _read_jsonl(MEMORY_PATH)


def delete_memory(index: int) -> bool:
    lines = [l for l in MEMORY_PATH.read_text(encoding="utf-8").splitlines() if l.strip()] if MEMORY_PATH.exists() else []
    if not (0 <= index < len(lines)):
        return False
    lines.pop(index)
    _rewrite_jsonl(MEMORY_PATH, lines)
    return True


def clear_memory() -> None:
    _rewrite_jsonl(MEMORY_PATH, [])


def delete_feedback(index: int) -> bool:
    lines = [l for l in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines() if l.strip()] if FEEDBACK_PATH.exists() else []
    if not (0 <= index < len(lines)):
        return False
    lines.pop(index)
    _rewrite_jsonl(FEEDBACK_PATH, lines)
    return True


def clear_feedback() -> None:
    _rewrite_jsonl(FEEDBACK_PATH, [])


def reset() -> None:
    with SessionLocal() as s:
        for t in (AlertArtifact, Alert, Artifact, Report, Case, AuditLog):
            s.execute(text(f"DELETE FROM {t.__tablename__}"))
        s.commit()


# ---- 基础写入 ----

def insert_case(correlation_uid: str, title: str, strength: float, entity_summary) -> int:
    with SessionLocal() as s:
        c = Case(correlation_uid=correlation_uid, title=title, strength=strength,
                 entity_summary=_as_list(entity_summary))
        s.add(c)
        s.commit()
        return c.id


def insert_alert(case_id: int, e) -> int:
    with SessionLocal() as s:
        a = Alert(case_id=case_id, time=e.time, source=e.source, asset=e.asset, type=e.etype,
                  raw=e.raw, confidence=e.confidence, reason=e.reason, innate=int(e.innate),
                  label=e.label, created_at=datetime_now())
        s.add(a)
        s.commit()
        return a.id


def insert_suppressed_alert(signal: dict, why: str) -> int:
    with SessionLocal() as s:
        a = Alert(case_id=None, time=signal.get("time", ""), source=signal.get("source", ""),
                  asset=signal.get("asset", ""), type=signal.get("type", ""),
                  raw=signal.get("raw", ""), confidence=signal.get("confidence"),
                  reason="", suppressed=1, why=why, created_at=datetime_now())
        s.add(a)
        s.commit()
        return a.id


def list_suppressed_alerts(limit: int = 200) -> list[dict]:
    with SessionLocal() as s:
        rows = s.execute(select(Alert).where(Alert.suppressed == 1).order_by(Alert.id.desc()).limit(limit)).scalars().all()
        return [_alert_row(a) for a in rows]


def count_historical_alerts(asset: str, type_: str, window_seconds: int) -> int:
    with SessionLocal() as s:
        q = select(func.count()).select_from(Alert).where(
            Alert.asset == asset, Alert.type == type_,
            Alert.created_at < func.datetime("now", f"-{window_seconds} seconds"),
        )
        return s.execute(q).scalar_one()


def get_alert(alert_id: int) -> dict | None:
    with SessionLocal() as s:
        a = s.get(Alert, alert_id)
        return _alert_row(a) if a else None


def delete_alert(alert_id: int) -> None:
    with SessionLocal() as s:
        a = s.get(Alert, alert_id)
        if a:
            s.delete(a)
            s.commit()


def get_or_create_artifact(type_: str, value: str) -> int:
    with SessionLocal() as s:
        art = s.execute(select(Artifact).where(Artifact.type == type_, Artifact.value == value)).scalar_one_or_none()
        if art:
            return art.id
        art = Artifact(type=type_, value=value)
        s.add(art)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            art = s.execute(select(Artifact).where(Artifact.type == type_, Artifact.value == value)).scalar_one()
        return art.id


def link_alert_artifact(alert_id: int, artifact_id: int) -> None:
    with SessionLocal() as s:
        s.add(AlertArtifact(alert_id=alert_id, artifact_id=artifact_id))
        s.commit()


def insert_report(case_id: int, report: dict) -> None:
    with SessionLocal() as s:
        r = s.execute(select(Report).where(Report.case_id == case_id)).scalar_one_or_none()
        if not r:
            r = Report(case_id=case_id)
            s.add(r)
        r.verdict = report.get("verdict", "")
        r.confidence = report.get("confidence", "")
        r.digest = report.get("digest", "")
        r.evidence_json = report.get("evidence", [])
        r.iocs_json = report.get("iocs", [])
        r.unknowns_json = report.get("unknowns", [])
        r.remediations_json = report.get("remediations", [])
        r.attack_chain_json = report.get("attack_chain", [])
        s.commit()


def insert_audit(action: str, entity: str, changes: str) -> None:
    with SessionLocal() as s:
        s.add(AuditLog(action=action, entity=entity, changes=changes))
        s.commit()


def datetime_now() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---- 内部资产清单 ----

def list_assets() -> list[dict]:
    with SessionLocal() as s:
        rows = s.execute(select(Asset).order_by(Asset.id)).scalars().all()
        return [{"role": a.role, "value": a.value, "criticality": a.criticality} for a in rows]


def replace_assets(rows: list[dict]) -> list[dict]:
    """整体替换资产清单（前端编辑完一次性保存）。rows: [{role, value, criticality}]。"""
    with SessionLocal() as s:
        s.execute(text("DELETE FROM assets"))
        for r in rows:
            s.add(Asset(role=(r.get("role") or "").strip(),
                        value=(r.get("value") or "").strip(),
                        criticality=r.get("criticality") or "normal"))
        s.commit()
    return list_assets()


# 复杂查询与聚合（re-export，保持 `from app.crud import list_cases` 等可用）。
from app.crud.queries import *  # noqa: E402,F401
