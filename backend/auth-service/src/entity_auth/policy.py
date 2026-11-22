from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from entity_auth.config import get_settings
from entity_auth.db import ActionApproval, DivisionMembership, SharedResourceGrant, TaskAssignment, User


DIVISIONS = {
    "mind", "reality", "human", "science", "engineering", "space", "planet", "future"
}
PERMISSIONS = {"read", "create", "modify", "approve", "execute", "administer", "revoke"}
RISK_LEVELS = {"low", "moderate", "high", "critical"}
APPROVAL_RANKS = {0}


@dataclass(frozen=True)
class AccessRequest:
    division: str
    action: str
    resource_type: str
    resource_id: str
    classification: str = "internal"
    risk: str = "low"
    environment: str = "development"
    task_id: str | None = None
    approval_id: str | None = None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def has_mfa(claims: dict) -> bool:
    configured = get_settings().mfa_methods
    amr = claims.get("amr", [])
    if isinstance(amr, str):
        amr = [amr]
    return bool({str(value).lower() for value in amr} & configured)


def has_recent_step_up(claims: dict) -> bool:
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, (int, float)) or not has_mfa(claims):
        return False
    age = datetime.now(timezone.utc).timestamp() - auth_time
    return 0 <= age <= get_settings().step_up_max_age_seconds


def _active_task(db: Session, subject: str, request: AccessRequest, now: datetime) -> TaskAssignment | None:
    if not request.task_id:
        return None
    task = db.scalar(select(TaskAssignment).where(
        TaskAssignment.id == request.task_id,
        TaskAssignment.subject == subject,
        TaskAssignment.division == request.division,
        TaskAssignment.revoked_at.is_(None),
        TaskAssignment.starts_at <= now,
        TaskAssignment.expires_at > now,
    ))
    if not task or request.action not in task.permissions:
        return None
    if task.resource_type and task.resource_type != request.resource_type:
        return None
    if task.resource_id and task.resource_id != request.resource_id:
        return None
    return task


def _has_grant(db: Session, subject: str, request: AccessRequest, now: datetime) -> bool:
    return db.scalar(select(SharedResourceGrant.id).where(
        SharedResourceGrant.subject == subject,
        SharedResourceGrant.resource_type == request.resource_type,
        SharedResourceGrant.resource_id == request.resource_id,
        SharedResourceGrant.permission == request.action,
        SharedResourceGrant.revoked_at.is_(None),
        (SharedResourceGrant.expires_at.is_(None) | (SharedResourceGrant.expires_at > now)),
    )) is not None


def _has_approval(db: Session, subject: str, request: AccessRequest, now: datetime) -> bool:
    if not request.approval_id:
        return False
    approval = db.get(ActionApproval, request.approval_id)
    if not approval:
        return False
    approver = db.get(User, approval.approver) if approval.approver else None
    return bool(
        approval.status == "approved"
        and approval.requester == subject
        and approval.approver != subject
        and approver and approver.active and approver.rank in APPROVAL_RANKS
        and approval.division == request.division
        and approval.action == request.action
        and approval.resource_type == request.resource_type
        and approval.resource_id == request.resource_id
        and approval.classification == request.classification
        and approval.risk == request.risk
        and approval.environment == request.environment
        and approval.task_id == request.task_id
        and approval.expires_at > now
    )


def authorize(
    db: Session,
    user: User,
    claims: dict,
    request: AccessRequest,
    *,
    require_independent_approval: bool = True,
) -> Decision:
    now = datetime.now(timezone.utc)
    if request.division not in DIVISIONS or request.action not in PERMISSIONS or request.risk not in RISK_LEVELS:
        return Decision(False, "invalid_scope")
    if request.classification not in {"public", "internal", "restricted", "highly_restricted"}:
        return Decision(False, "invalid_classification")
    if request.environment not in {"development", "staging", "production"}:
        return Decision(False, "invalid_environment")
    if request.action == "execute" and request.environment != "production":
        return Decision(False, "execution_disabled_outside_production")
    if not user.active:
        return Decision(False, "account_disabled")
    if user.rank <= get_settings().privileged_max_rank and not has_mfa(claims):
        return Decision(False, "mfa_required")
    if request.action in {"approve", "execute", "administer", "revoke"} and not has_recent_step_up(claims):
        return Decision(False, "fresh_mfa_required")

    member = db.scalar(select(DivisionMembership.id).where(
        DivisionMembership.subject == user.subject,
        DivisionMembership.division == request.division,
    )) is not None
    task = _active_task(db, user.subject, request, now)
    shared = _has_grant(db, user.subject, request, now)
    owner = user.rank == 0

    # Guest access is always explicit and resource-specific.
    if user.rank == 6:
        if request.action == "read" and request.classification == "public" and shared:
            return Decision(True, "explicit_public_share")
        return Decision(False, "explicit_share_required")

    if not owner and not member and not shared:
        return Decision(False, "division_membership_required")
    if request.classification in {"restricted", "highly_restricted"} and not owner and not task:
        return Decision(False, "restricted_task_assignment_required")

    # Baseline authority by rank. Assignments can scope operations; they do not raise a user's rank.
    if request.action == "read":
        baseline = user.rank <= 5
    elif request.action in {"create", "modify"}:
        baseline = user.rank <= 5 and (user.rank <= 3 or task is not None)
    elif request.action == "approve":
        baseline = user.rank <= 3 and task is not None
    elif request.action == "execute":
        baseline = user.rank <= 4 and task is not None
    else:
        # Administrative and revocation powers are not inferred from a rank alone.
        baseline = owner and task is not None
    if not owner and not baseline and not shared:
        return Decision(False, "rank_or_assignment_insufficient")
    if require_independent_approval and request.risk in {"high", "critical"} and request.action in {"execute", "approve"}:
        if not _has_approval(db, user.subject, request, now):
            return Decision(False, "independent_approval_required")
    return Decision(True, "owner_authority" if owner else "authorized")
