from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint, create_engine, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from entity_auth.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "entity_users"
    __table_args__ = (
        UniqueConstraint("subject", name="uq_entity_users_subject"),
        CheckConstraint("rank BETWEEN 0 AND 6", name="ck_entity_user_rank"),
        Index(
            "uq_entity_single_owner", "rank", unique=True,
            postgresql_where=text("rank = 0"), sqlite_where=text("rank = 0"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255))


class DivisionMembership(Base):
    __tablename__ = "entity_division_memberships"
    __table_args__ = (UniqueConstraint("subject", "division", name="uq_subject_division"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject: Mapped[str] = mapped_column(ForeignKey("entity_users.subject", ondelete="CASCADE"), index=True)
    division: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    assigned_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TaskAssignment(Base):
    __tablename__ = "entity_task_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject: Mapped[str] = mapped_column(ForeignKey("entity_users.subject", ondelete="CASCADE"), index=True)
    division: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[str] = mapped_column(String(255), nullable=False)


class SharedResourceGrant(Base):
    __tablename__ = "entity_shared_resource_grants"
    __table_args__ = (UniqueConstraint("subject", "resource_type", "resource_id", "permission", name="uq_resource_grant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject: Mapped[str] = mapped_column(ForeignKey("entity_users.subject", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(24), nullable=False)
    granted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResourcePolicy(Base):
    __tablename__ = "entity_resource_policies"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('public', 'internal', 'restricted', 'highly_restricted')",
            name="ck_resource_policy_classification",
        ),
        CheckConstraint(
            "risk IN ('low', 'moderate', 'high', 'critical')",
            name="ck_resource_policy_risk",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_resource_policy_version",
        ),
    )

    resource_type: Mapped[str] = mapped_column(String(80), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    owner_subject: Mapped[str] = mapped_column(
        ForeignKey("entity_users.subject", ondelete="RESTRICT"), nullable=False, index=True
    )
    division: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TokenSession(Base):
    __tablename__ = "entity_token_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject: Mapped[str] = mapped_column(ForeignKey("entity_users.subject", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionApproval(Base):
    __tablename__ = "entity_action_approvals"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_action_approval_status"),
        CheckConstraint("required_approver_rank IN (0, 1)", name="ck_action_approval_reviewer_rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requester: Mapped[str] = mapped_column(ForeignKey("entity_users.subject"), nullable=False, index=True)
    approver: Mapped[str | None] = mapped_column(String(255), index=True)
    division: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resource_owner_subject: Mapped[str | None] = mapped_column(String(255))
    resource_version: Mapped[int | None] = mapped_column(Integer)
    required_approver_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminChange(Base):
    __tablename__ = "entity_admin_changes"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_admin_change_status"),
        CheckConstraint("required_approver_rank = 1", name="ck_admin_change_reviewer_rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requester: Mapped[str] = mapped_column(ForeignKey("entity_users.subject"), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    required_approver_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    approver: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "entity_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
