from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from entity_auth.config import get_settings
from entity_auth.db import (
    ActionApproval, AuditEvent, SessionLocal, SharedResourceGrant, TaskAssignment, TokenSession, User, utcnow,
)
from entity_auth.oidc import verify_bearer
from entity_auth.policy import AccessRequest, DIVISIONS, PERMISSIONS, authorize, has_mfa, has_recent_step_up


app = FastAPI(title="ENTITY Identity and Authorization", version="0.1.0")
bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def append_audit(db: Session, actor: str, event_type: str, outcome: str, detail: dict) -> None:
    # Serialize the append and link each event to the prior HMAC. The HMAC key must live
    # outside PostgreSQL so a database-only edit cannot silently rewrite the event chain.
    db.execute(text("SELECT pg_advisory_xact_lock(7408216301)"))
    tail_hash = db.scalar(select(AuditEvent.event_hash).where(
        ~AuditEvent.event_hash.in_(select(AuditEvent.previous_hash))
    ).limit(1))
    prev_hash = tail_hash or "0" * 64
    created_at = utcnow()
    record = {
        "id": str(uuid4()), "created_at": created_at.isoformat(), "actor": actor,
        "event_type": event_type, "outcome": outcome, "detail": detail,
        "previous_hash": prev_hash,
    }
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    event_hash = hmac.new(get_settings().audit_hmac_key.encode(), payload, hashlib.sha256).hexdigest()
    db.add(AuditEvent(
        id=record["id"], created_at=created_at, actor=actor, event_type=event_type,
        outcome=outcome, detail=detail, previous_hash=prev_hash, event_hash=event_hash,
    ))
    db.flush()


class Principal:
    def __init__(self, user: User, claims: dict, session: TokenSession):
        self.user, self.claims, self.session = user, claims, session


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        verified = verify_bearer(credentials.credentials)
    except (jwt.PyJWTError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="Invalid identity token", headers={"WWW-Authenticate": "Bearer"}) from exc

    subject = verified.claims["sub"]
    user = db.scalar(select(User).where(User.subject == subject))
    if not user or not user.active:
        raise HTTPException(status_code=403, detail="Account is not provisioned or is suspended")
    if user.rank <= get_settings().privileged_max_rank and not has_mfa(verified.claims):
        raise HTTPException(status_code=403, detail="MFA is required for privileged accounts")

    expiry = datetime.fromtimestamp(verified.claims["exp"], timezone.utc)
    now = utcnow()
    stmt = insert(TokenSession).values(
        id=str(uuid4()), subject=subject, token_hash=verified.token_hash,
        expires_at=expiry, created_at=now, last_seen_at=now,
    ).on_conflict_do_nothing(index_elements=["token_hash"])
    insert_result = db.execute(stmt)
    token_session = db.scalar(select(TokenSession).where(TokenSession.token_hash == verified.token_hash))
    if not token_session or token_session.revoked_at or token_session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session revoked or expired", headers={"WWW-Authenticate": "Bearer"})
    db.execute(update(TokenSession).where(TokenSession.id == token_session.id).values(last_seen_at=now))
    if insert_result.rowcount == 1:
        append_audit(db, subject, "session.started", "success", {"session_id": token_session.id})
    db.commit()
    return Principal(user, verified.claims, token_session)


def owner_only(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
    if principal.user.rank != 0:
        raise HTTPException(status_code=403, detail="Owner authorization required")
    if not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="Recent MFA authentication is required")
    return principal


class AccessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    division: str
    action: str
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    classification: str = "internal"
    risk: str = "low"
    task_id: str | None = None
    approval_id: str | None = None


class ProvisionUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=255)
    rank: int = Field(ge=1, le=6)
    divisions: list[str] = Field(default_factory=list)


class UpdateUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rank: int | None = Field(default=None, ge=1, le=6)
    active: bool | None = None
    divisions: list[str] | None = None


class TaskAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=255)
    division: str
    description: str = Field(min_length=1, max_length=2000)
    permissions: list[str] = Field(min_length=1)
    resource_type: str | None = Field(default=None, max_length=80)
    resource_id: str | None = Field(default=None, max_length=255)
    expires_at: datetime


class ResourceShareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=255)
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    permission: str = "read"
    expires_at: datetime | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    division: str
    action: str
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    classification: str
    risk: str
    task_id: str = Field(min_length=1, max_length=36)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/v1/auth/me")
def me(principal: Annotated[Principal, Depends(current_principal)], db: Annotated[Session, Depends(get_db)]):
    from entity_auth.db import DivisionMembership
    divisions = list(db.scalars(select(DivisionMembership.division).where(
        DivisionMembership.subject == principal.user.subject
    )).all())
    return {
        "subject": principal.user.subject,
        "rank": principal.user.rank,
        "active": principal.user.active,
        "divisions": divisions,
        "session_id": principal.session.id,
        "expires_at": principal.session.expires_at,
    }


@app.get("/v1/auth/sessions")
def list_sessions(principal: Annotated[Principal, Depends(current_principal)], db: Annotated[Session, Depends(get_db)]):
    now = utcnow()
    sessions = db.scalars(select(TokenSession).where(
        TokenSession.subject == principal.user.subject,
        TokenSession.expires_at > now,
    ).order_by(TokenSession.last_seen_at.desc())).all()
    return [{
        "id": item.id, "created_at": item.created_at, "last_seen_at": item.last_seen_at,
        "expires_at": item.expires_at, "revoked": item.revoked_at is not None,
        "current": item.id == principal.session.id,
    } for item in sessions]


@app.delete("/v1/auth/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    target = db.scalar(select(TokenSession).where(
        TokenSession.id == session_id, TokenSession.subject == principal.user.subject
    ))
    if not target:
        raise HTTPException(status_code=404, detail="Session not found")
    if not target.revoked_at:
        target.revoked_at = utcnow()
        append_audit(db, principal.user.subject, "session.revoked", "success", {"session_id": session_id})
        db.commit()


@app.post("/v1/access/check")
def access_check(
    body: AccessCheck,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    request = AccessRequest(**body.model_dump(), environment=get_settings().environment)
    decision = authorize(db, principal.user, principal.claims, request)
    append_audit(db, principal.user.subject, "access.check", "allow" if decision.allowed else "deny", {
        "division": body.division, "action": body.action, "resource_type": body.resource_type,
        "resource_id": body.resource_id, "classification": body.classification,
        "risk": body.risk, "reason": decision.reason,
    })
    db.commit()
    return {"allowed": decision.allowed, "reason": decision.reason}


@app.post("/v1/admin/users", status_code=201)
def provision_user(
    body: ProvisionUser,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    if any(division not in DIVISIONS for division in body.divisions):
        raise HTTPException(status_code=422, detail="Unknown division")
    if db.scalar(select(User).where(User.subject == body.subject)):
        raise HTTPException(status_code=409, detail="Identity already provisioned")
    user = User(subject=body.subject, rank=body.rank, active=True, created_by=principal.user.subject)
    db.add(user)
    for division in sorted(set(body.divisions)):
        from entity_auth.db import DivisionMembership
        db.add(DivisionMembership(subject=body.subject, division=division, assigned_by=principal.user.subject))
    append_audit(db, principal.user.subject, "user.provisioned", "success", {
        "subject": body.subject, "rank": body.rank, "divisions": sorted(set(body.divisions)),
    })
    db.commit()
    return {"subject": user.subject, "rank": user.rank, "active": user.active}


@app.post("/v1/admin/users/{subject}/suspend", status_code=204)
def suspend_user(
    subject: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    if subject == principal.user.subject:
        raise HTTPException(status_code=409, detail="Owner cannot suspend the active owner account")
    user = db.scalar(select(User).where(User.subject == subject))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.active = False
    db.execute(update(TokenSession).where(
        TokenSession.subject == subject, TokenSession.revoked_at.is_(None)
    ).values(revoked_at=utcnow()))
    append_audit(db, principal.user.subject, "user.suspended", "success", {"subject": subject})
    db.commit()


@app.patch("/v1/admin/users/{subject}")
def update_user(
    subject: str,
    body: UpdateUser,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    from entity_auth.db import DivisionMembership
    if subject == principal.user.subject:
        raise HTTPException(status_code=409, detail="Owner cannot change their own rank or status")
    if body.rank is None and body.active is None and body.divisions is None:
        raise HTTPException(status_code=422, detail="At least one user field must be updated")
    if body.divisions is not None and any(division not in DIVISIONS for division in body.divisions):
        raise HTTPException(status_code=422, detail="Unknown division")
    user = db.scalar(select(User).where(User.subject == subject))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes: dict = {}
    if body.rank is not None and body.rank != user.rank:
        changes["rank"] = {"from": user.rank, "to": body.rank}
        user.rank = body.rank
    if body.active is not None and body.active != user.active:
        changes["active"] = {"from": user.active, "to": body.active}
        user.active = body.active
        if not body.active:
            db.execute(update(TokenSession).where(
                TokenSession.subject == subject, TokenSession.revoked_at.is_(None)
            ).values(revoked_at=utcnow()))
    if body.divisions is not None:
        current = set(db.scalars(select(DivisionMembership.division).where(
            DivisionMembership.subject == subject
        )).all())
        desired = set(body.divisions)
        if current != desired:
            changes["divisions"] = {"from": sorted(current), "to": sorted(desired)}
            db.execute(delete(DivisionMembership).where(DivisionMembership.subject == subject))
            for division in sorted(desired):
                db.add(DivisionMembership(
                    subject=subject, division=division, assigned_by=principal.user.subject
                ))
    if not changes:
        return {"subject": user.subject, "rank": user.rank, "active": user.active, "changed": False}
    append_audit(db, principal.user.subject, "user.access_updated", "success", {
        "subject": subject, "changes": changes,
    })
    db.commit()
    return {"subject": user.subject, "rank": user.rank, "active": user.active, "changed": True}


@app.post("/v1/admin/tasks", status_code=201)
def assign_task(
    body: TaskAssignmentInput,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    from entity_auth.db import DivisionMembership, TaskAssignment
    target = db.scalar(select(User).where(User.subject == body.subject, User.active.is_(True)))
    is_member = db.scalar(select(DivisionMembership.id).where(
        DivisionMembership.subject == body.subject, DivisionMembership.division == body.division
    ))
    now = utcnow()
    if not target or not is_member:
        raise HTTPException(status_code=404, detail="Active division member not found")
    if body.division not in DIVISIONS or not set(body.permissions) <= PERMISSIONS:
        raise HTTPException(status_code=422, detail="Unknown division or permission")
    if body.expires_at.tzinfo is None or body.expires_at <= now or body.expires_at > now + timedelta(days=365):
        raise HTTPException(status_code=422, detail="Task expiry must be timezone-aware and within one year")
    task = TaskAssignment(
        subject=body.subject, division=body.division, description=body.description,
        permissions=sorted(set(body.permissions)), resource_type=body.resource_type,
        resource_id=body.resource_id, expires_at=body.expires_at,
        assigned_by=principal.user.subject,
    )
    db.add(task)
    append_audit(db, principal.user.subject, "task.assigned", "success", {
        "task_id": task.id, "subject": body.subject, "division": body.division,
        "permissions": sorted(set(body.permissions)), "expires_at": body.expires_at.isoformat(),
    })
    db.commit()
    return {"task_id": task.id, "subject": task.subject, "division": task.division,
            "permissions": task.permissions, "expires_at": task.expires_at}


@app.post("/v1/admin/resources/shares", status_code=201)
def share_resource(
    body: ResourceShareInput,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    from entity_auth.db import SharedResourceGrant
    target = db.scalar(select(User).where(User.subject == body.subject, User.active.is_(True)))
    if not target:
        raise HTTPException(status_code=404, detail="Active user not found")
    if body.permission != "read":
        raise HTTPException(status_code=422, detail="Explicit resource shares are read-only")
    if body.expires_at and (body.expires_at.tzinfo is None or body.expires_at <= utcnow()):
        raise HTTPException(status_code=422, detail="Share expiry must be a future timezone-aware timestamp")
    grant = SharedResourceGrant(
        subject=body.subject, resource_type=body.resource_type, resource_id=body.resource_id,
        permission=body.permission, granted_by=principal.user.subject, expires_at=body.expires_at,
    )
    db.add(grant)
    append_audit(db, principal.user.subject, "resource.shared", "success", {
        "subject": body.subject, "resource_type": body.resource_type,
        "resource_id": body.resource_id, "permission": body.permission,
        "expires_at": body.expires_at.isoformat() if body.expires_at else None,
    })
    db.commit()
    return {"share_id": grant.id, "subject": grant.subject, "permission": grant.permission}


@app.post("/v1/admin/tasks/{task_id}/revoke", status_code=204)
def revoke_task(
    task_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    task = db.get(TaskAssignment, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task assignment not found")
    if not task.revoked_at:
        task.revoked_at = utcnow()
        append_audit(db, principal.user.subject, "task.revoked", "success", {"task_id": task_id})
        db.commit()


@app.post("/v1/admin/resources/shares/{share_id}/revoke", status_code=204)
def revoke_share(
    share_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    share = db.get(SharedResourceGrant, share_id)
    if not share:
        raise HTTPException(status_code=404, detail="Resource share not found")
    if not share.revoked_at:
        share.revoked_at = utcnow()
        append_audit(db, principal.user.subject, "resource.share_revoked", "success", {"share_id": share_id})
        db.commit()


@app.post("/v1/approvals", status_code=201)
def request_approval(
    body: ApprovalRequest,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    if body.division not in DIVISIONS or body.action not in {"execute", "approve"} or body.risk not in {"high", "critical"}:
        raise HTTPException(status_code=422, detail="Approval requests are for high-risk execution or approval actions")
    if principal.user.rank == 0:
        raise HTTPException(status_code=403, detail="Owner cannot request an approval for their own action")
    if principal.user.rank > 4:
        raise HTTPException(status_code=403, detail="Rank is not eligible to request operational approval")
    request = AccessRequest(
        division=body.division, action=body.action, resource_type=body.resource_type,
        resource_id=body.resource_id, classification=body.classification,
        risk=body.risk, environment=get_settings().environment, task_id=body.task_id,
    )
    scope = authorize(db, principal.user, principal.claims, request, require_independent_approval=False)
    if not scope.allowed:
        raise HTTPException(status_code=403, detail=f"Action is outside the requester's authority: {scope.reason}")
    approval = ActionApproval(
        requester=principal.user.subject, division=body.division, action=body.action,
        resource_type=body.resource_type, resource_id=body.resource_id,
        classification=body.classification, risk=body.risk, environment=request.environment,
        task_id=body.task_id,
        expires_at=utcnow() + timedelta(hours=8),
    )
    db.add(approval)
    append_audit(db, principal.user.subject, "approval.requested", "pending", {
        "approval_id": approval.id, "division": body.division, "action": body.action,
        "resource_type": body.resource_type, "resource_id": body.resource_id,
        "classification": body.classification, "risk": body.risk,
        "environment": request.environment, "task_id": body.task_id,
    })
    db.commit()
    return {"approval_id": approval.id, "status": approval.status, "expires_at": approval.expires_at}


@app.get("/v1/approvals/pending")
def pending_approvals(
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    now = utcnow()
    items = db.scalars(select(ActionApproval).where(
        ActionApproval.status == "pending", ActionApproval.expires_at > now,
        ActionApproval.requester != principal.user.subject,
    ).order_by(ActionApproval.created_at.asc())).all()
    return [{
        "approval_id": item.id, "requester": item.requester, "division": item.division,
        "action": item.action, "resource_type": item.resource_type,
        "resource_id": item.resource_id, "classification": item.classification,
        "risk": item.risk, "environment": item.environment, "task_id": item.task_id,
        "created_at": item.created_at, "expires_at": item.expires_at,
    } for item in items]


@app.post("/v1/approvals/{approval_id}/approve")
def decide_approval(
    approval_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    approval = db.get(ActionApproval, approval_id)
    now = utcnow()
    if not approval or approval.status != "pending" or approval.expires_at <= now:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    if approval.requester == principal.user.subject:
        raise HTTPException(status_code=403, detail="Self-approval is prohibited")
    if principal.user.rank != 0:
        raise HTTPException(status_code=403, detail="Only the Owner can approve this request")
    if not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="Recent MFA authentication is required")
    # Conditional update prevents two approvers from both deciding the same request.
    result = db.execute(update(ActionApproval).where(
        ActionApproval.id == approval_id, ActionApproval.status == "pending"
    ).values(status="approved", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval was already decided")
    append_audit(db, principal.user.subject, "approval.decided", "approved", {
        "approval_id": approval_id, "requester": approval.requester,
    })
    db.commit()
    return {"approval_id": approval_id, "status": "approved"}


@app.post("/v1/approvals/{approval_id}/reject")
def reject_approval(
    approval_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    approval = db.get(ActionApproval, approval_id)
    now = utcnow()
    if not approval or approval.status != "pending" or approval.expires_at <= now:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    if approval.requester == principal.user.subject:
        raise HTTPException(status_code=403, detail="Requester cannot decide their own request")
    result = db.execute(update(ActionApproval).where(
        ActionApproval.id == approval_id, ActionApproval.status == "pending"
    ).values(status="rejected", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval was already decided")
    append_audit(db, principal.user.subject, "approval.decided", "rejected", {
        "approval_id": approval_id, "requester": approval.requester,
    })
    db.commit()
    return {"approval_id": approval_id, "status": "rejected"}


@app.get("/v1/admin/audit/verify")
def verify_audit_chain(
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    key = get_settings().audit_hmac_key.encode()
    events = db.scalars(select(AuditEvent)).all()
    children: dict[str, list[AuditEvent]] = {}
    for event in events:
        children.setdefault(event.previous_hash, []).append(event)
    previous = "0" * 64
    visited: set[str] = set()
    valid = True
    while children.get(previous):
        next_events = children[previous]
        if len(next_events) != 1:
            valid = False
            break
        event = next_events[0]
        record = {
            "id": event.id,
            "created_at": event.created_at.isoformat(),
            "actor": event.actor,
            "event_type": event.event_type,
            "outcome": event.outcome,
            "detail": event.detail,
            "previous_hash": event.previous_hash,
        }
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, event.event_hash):
            valid = False
            break
        visited.add(event.id)
        previous = event.event_hash
    valid = valid and len(visited) == len(events)
    return {"valid": valid, "events_checked": len(visited), "event_count": len(events)}
