from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from entity_auth.config import get_settings
from entity_auth.db import (
    ActionApproval, DivisionMembership, ResourcePolicy, SharedResourceGrant, TaskAssignment, User,
)


DIVISIONS = {
    "mind", "reality", "human", "science", "engineering", "space", "planet", "future"
}
PERMISSIONS = {"read", "create", "modify", "approve", "execute", "administer", "revoke"}
RISK_LEVELS = {"low", "moderate", "high", "critical"}
CLASSIFICATIONS = {"public", "internal", "restricted", "highly_restricted"}


@dataclass(frozen=True)
class AccessRequest:
    # These are references and requested actions only. Security context is resolved from ResourcePolicy.
    action: str
    resource_type: str
    resource_id: str
    environment: str
    task_id: str | None = None
    approval_id: str | None = None


@dataclass(frozen=True)
class ResourceContext:
    resource_type: str
    resource_id: str
    resource_owner_subject: str
    division: str
    classification: str
    risk: str
    version: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    context: ResourceContext | None = None


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


def resolve_resource_context(db: Session, request: AccessRequest) -> ResourceContext | None:
    resource = db.get(ResourcePolicy, (request.resource_type, request.resource_id))
    if resource is None:
        return None
    return ResourceContext(
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        resource_owner_subject=resource.owner_subject,
        division=resource.division,
        classification=resource.classification,
        risk=resource.risk,
        version=resource.version,
    )


def _active_task(
    db: Session, subject: str, request: AccessRequest, context: ResourceContext, now: datetime
) -> TaskAssignment | None:
    if not request.task_id:
        return None
    task = db.scalar(select(TaskAssignment).where(
        TaskAssignment.id == request.task_id,
        TaskAssignment.subject == subject,
        TaskAssignment.division == context.division,
        TaskAssignment.revoked_at.is_(None),
        TaskAssignment.starts_at <= now,
        TaskAssignment.expires_at > now,
    ))
    if not task or request.action not in task.permissions:
        return None
    if task.resource_type and task.resource_type != context.resource_type:
        return None
    if task.resource_id and task.resource_id != context.resource_id:
        return None
    return task


def _has_grant(db: Session, subject: str, request: AccessRequest, now: datetime) -> bool:
    # Explicit shares are deliberately read-only, including grants created by older versions.
    if request.action != "read":
        return False
    return db.scalar(select(SharedResourceGrant.id).where(
        SharedResourceGrant.subject == subject,
        SharedResourceGrant.resource_type == request.resource_type,
        SharedResourceGrant.resource_id == request.resource_id,
        SharedResourceGrant.permission == "read",
        SharedResourceGrant.revoked_at.is_(None),
        (SharedResourceGrant.expires_at.is_(None) | (SharedResourceGrant.expires_at > now)),
    )) is not None


def _has_approval(
    db: Session,
    subject: str,
    requester_rank: int,
    request: AccessRequest,
    context: ResourceContext,
    now: datetime,
) -> bool:
    if not request.approval_id:
        return False
    approval = db.get(ActionApproval, request.approval_id)
    if not approval:
        return False
    approver = db.scalar(select(User).where(User.subject == approval.approver)) if approval.approver else None
    required_rank = 1 if requester_rank == 0 else 0
    return bool(
        approval.status == "approved"
        and approval.consumed_at is None
        and approval.requester == subject
        and approval.approver != subject
        and approval.required_approver_rank == required_rank
        and approver and approver.active and approver.rank == required_rank
        and approval.division == context.division
        and approval.action == request.action
        and approval.resource_type == context.resource_type
        and approval.resource_id == context.resource_id
        and approval.resource_owner_subject == context.resource_owner_subject
        and approval.resource_version == context.version
        and approval.classification == context.classification
        and approval.risk == context.risk
        and approval.environment == request.environment
        and approval.task_id == request.task_id
        and approval.decided_at is not None
        and approval.expires_at > now
    )


def consume_approval(
    db: Session,
    subject: str,
    requester_rank: int,
    request: AccessRequest,
    context: ResourceContext,
    now: datetime | None = None,
) -> bool:
    """Atomically consume one exact, still-approved high-risk decision."""
    if not request.approval_id:
        return False
    now = now or datetime.now(timezone.utc)
    required_rank = 1 if requester_rank == 0 else 0
    approver_is_active = select(User.id).where(
        User.subject == ActionApproval.approver,
        User.active.is_(True),
        User.rank == required_rank,
    ).exists()
    requester_is_active = select(User.id).where(
        User.subject == subject, User.active.is_(True), User.rank == requester_rank,
    ).exists()
    task_is_current = select(TaskAssignment.id).where(
        TaskAssignment.id == request.task_id,
        TaskAssignment.subject == subject,
        TaskAssignment.division == context.division,
        TaskAssignment.revoked_at.is_(None),
        TaskAssignment.starts_at <= now,
        TaskAssignment.expires_at > now,
        (TaskAssignment.resource_type.is_(None) | (TaskAssignment.resource_type == context.resource_type)),
        (TaskAssignment.resource_id.is_(None) | (TaskAssignment.resource_id == context.resource_id)),
    ).exists()
    policy_is_current = select(ResourcePolicy.resource_type).where(
        ResourcePolicy.resource_type == context.resource_type,
        ResourcePolicy.resource_id == context.resource_id,
        ResourcePolicy.owner_subject == context.resource_owner_subject,
        ResourcePolicy.division == context.division,
        ResourcePolicy.classification == context.classification,
        ResourcePolicy.risk == context.risk,
        ResourcePolicy.version == context.version,
    ).exists()
    result = db.execute(update(ActionApproval).where(
        ActionApproval.id == request.approval_id,
        ActionApproval.status == "approved",
        ActionApproval.consumed_at.is_(None),
        ActionApproval.requester == subject,
        ActionApproval.approver != subject,
        ActionApproval.required_approver_rank == required_rank,
        ActionApproval.division == context.division,
        ActionApproval.action == request.action,
        ActionApproval.resource_type == context.resource_type,
        ActionApproval.resource_id == context.resource_id,
        ActionApproval.resource_owner_subject == context.resource_owner_subject,
        ActionApproval.resource_version == context.version,
        ActionApproval.classification == context.classification,
        ActionApproval.risk == context.risk,
        ActionApproval.environment == request.environment,
        ActionApproval.task_id == request.task_id,
        ActionApproval.expires_at > now,
        ActionApproval.decided_at.is_not(None),
        ActionApproval.approver.is_not(None),
        approver_is_active,
        requester_is_active,
        task_is_current,
        policy_is_current,
    ).values(consumed_at=now))
    return result.rowcount == 1


def requires_independent_approval(request: AccessRequest, context: ResourceContext) -> bool:
    return (
        context.risk in {"high", "critical"}
        or context.classification == "highly_restricted"
        or request.action in {"execute", "administer", "revoke"}
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
    if request.action not in PERMISSIONS:
        return Decision(False, "invalid_action")
    if request.environment not in {"development", "staging", "production"}:
        return Decision(False, "invalid_environment")
    if request.action == "execute" and request.environment != "production":
        return Decision(False, "execution_disabled_outside_production")
    if not user.active:
        return Decision(False, "account_disabled")
    if user.rank <= get_settings().privileged_max_rank and not has_mfa(claims):
        return Decision(False, "mfa_required")

    context = resolve_resource_context(db, request)
    if context is None:
        return Decision(False, "resource_not_registered")
    if context.division not in DIVISIONS or context.risk not in RISK_LEVELS:
        return Decision(False, "invalid_resource_policy", context)
    if context.classification not in CLASSIFICATIONS:
        return Decision(False, "invalid_resource_policy", context)

    high_risk = context.risk in {"high", "critical"}
    high_classification = context.classification == "highly_restricted"
    approval_required = requires_independent_approval(request, context)
    if request.action in {"approve", "execute", "administer", "revoke"} or high_risk or high_classification:
        if not has_recent_step_up(claims):
            return Decision(False, "fresh_mfa_required", context)

    member = db.scalar(select(DivisionMembership.id).where(
        DivisionMembership.subject == user.subject,
        DivisionMembership.division == context.division,
    )) is not None
    task = _active_task(db, user.subject, request, context, now)
    shared = _has_grant(db, user.subject, request, now)
    root_owner = user.rank == 0
    resource_owner = user.subject == context.resource_owner_subject

    if (high_risk or high_classification) and task is None:
        return Decision(False, "high_risk_task_assignment_required", context)

    # Guest access always needs an explicit share, even when the guest owns the resource.
    if user.rank == 6:
        if request.action == "read" and context.classification == "public" and shared:
            if require_independent_approval and approval_required and not _has_approval(
                db, user.subject, user.rank, request, context, now
            ):
                return Decision(False, "independent_approval_required", context)
            return Decision(True, "explicit_public_share", context)
        return Decision(False, "explicit_share_required", context)

    if not root_owner and not resource_owner and not member and not shared:
        return Decision(False, "division_membership_required", context)
    if context.classification in {"restricted", "highly_restricted"} and not task:
        return Decision(False, "restricted_task_assignment_required", context)

    # Resource ownership scopes access to the exact registered resource; it does not raise rank.
    if request.action == "read":
        baseline = user.rank <= 5
    elif request.action in {"create", "modify"}:
        baseline = user.rank <= 5 and (user.rank <= 3 or task is not None or resource_owner)
    elif request.action == "approve":
        baseline = user.rank <= 3 and task is not None
    elif request.action == "execute":
        baseline = user.rank <= 4 and task is not None
    else:
        baseline = root_owner and task is not None

    if not root_owner and not baseline and not shared:
        return Decision(False, "rank_or_assignment_insufficient", context)
    if require_independent_approval and approval_required and not _has_approval(
        db, user.subject, user.rank, request, context, now
    ):
        return Decision(False, "independent_approval_required", context)
    return Decision(True, "owner_authority" if root_owner else "authorized", context)
