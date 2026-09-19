"""SQLAlchemy ORM 模型（对应旧 db.py 的 7 张表）。

字段默认值、索引与旧 SCHEMA 完全对齐；created_at 用 SQLite `datetime('now')`（UTC，
YYYY-MM-DD HH:MM:SS），保留 alert_trend / count_historical_alerts 依赖的 strftime 语义。
"""
from __future__ import annotations

from sqlalchemy import (String, Integer, Float, Boolean, JSON, ForeignKey,
                        UniqueConstraint, Index, Text, text)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="user")
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, server_default=text("(datetime('now'))"))


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_uid: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String, default="")
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="New")
    verdict: Mapped[str] = mapped_column(String, default="")
    severity: Mapped[str] = mapped_column(String, default="")
    risk: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    entity_summary: Mapped[list] = mapped_column(JSON, default=list)
    disposition_note: Mapped[str] = mapped_column(String, default="")
    reported_at_alerts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, server_default=text("(datetime('now'))"))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_asset_type_created", "asset", "type", "created_at"),
        Index("idx_alerts_case_id", "case_id"),
        Index("idx_alerts_created_at", "created_at"),
        Index("idx_alerts_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cases.id"), nullable=True)
    time: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="")
    asset: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="")
    raw: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String, default="")
    innate: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String, default="")
    suppressed: Mapped[int] = mapped_column(Integer, default=0)
    why: Mapped[str] = mapped_column(String, default="")
    verdict: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String, server_default=text("(datetime('now'))"))


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("type", "value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)


class AlertArtifact(Base):
    __tablename__ = "alert_artifacts"
    __table_args__ = (
        Index("idx_alert_artifacts_alert_id", "alert_id"),
        Index("idx_alert_artifacts_artifact_id", "artifact_id"),
    )

    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("alerts.id"), primary_key=True)
    artifact_id: Mapped[int] = mapped_column(Integer, ForeignKey("artifacts.id"), primary_key=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id"), unique=True)
    verdict: Mapped[str] = mapped_column(String, default="")
    confidence: Mapped[str] = mapped_column(String, default="")
    digest: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    iocs_json: Mapped[list] = mapped_column(JSON, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, default=list)
    remediations_json: Mapped[list] = mapped_column(JSON, default=list)
    attack_chain_json: Mapped[list] = mapped_column(JSON, default=list)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String, default="")
    entity: Mapped[str] = mapped_column(String, default="")
    changes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String, server_default=text("(datetime('now'))"))


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (Index("idx_assets_role", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String, default="")
    value: Mapped[str] = mapped_column(String, default="")
    criticality: Mapped[str] = mapped_column(String, default="normal")
    created_at: Mapped[str] = mapped_column(String, server_default=text("(datetime('now'))"))
