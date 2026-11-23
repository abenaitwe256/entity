from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
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
    ActionApproval, AdminChange, AuditEvent, ResourcePolicy, SessionLocal, SharedResourceGrant,
    TaskAssignment, TokenSession, User, utcnow,
)
from entity_auth.oidc import verify_bearer
from entity_auth.policy import (
    AccessRequest, CLASSIFICATIONS, Decision, DIVISIONS, PERMISSIONS, RISK_LEVELS,
    authorize, consume_approval, has_mfa, has_recent_step_up, requires_independent_approval,
)


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


def _track_token_session(db: Session, user: User, verified) -> TokenSession:
    subject = user.subject
    expiry = datetime.fromtimestamp(verified.claims["exp"], timezone.utc)
    now = utcnow()
    stmt = insert(TokenSession).values(
        id=str(uuid4()), subject=subject, token_hash=verified.token_hash,
        expires_at=expiry, created_at=now, last_seen_at=now,
    ).on_conflict_do_nothing(index_elements=["token_hash"])
    insert_result = db.execute(stmt)
    token_session = db.scalar(select(TokenSession).where(TokenSession.token_hash == verified.token_hash))
    if (not token_session or token_session.subject != subject
            or token_session.revoked_at or token_session.expires_at <= now):
        raise HTTPException(status_code=401, detail="Session revoked or expired", headers={"WWW-Authenticate": "Bearer"})
    db.execute(update(TokenSession).where(TokenSession.id == token_session.id).values(last_seen_at=now))
    if insert_result.rowcount == 1:
        append_audit(db, subject, "session.started", "success", {"session_id": token_session.id})
    db.commit()
    return token_session


def _bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Principal:
    try:
        verified = verify_bearer(_bearer_token(credentials))
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="Invalid identity token", headers={"WWW-Authenticate": "Bearer"}) from exc

    subject = verified.claims["sub"]
    user = db.scalar(select(User).where(User.subject == subject))
    if not user or not user.active:
        raise HTTPException(status_code=403, detail="Account is not provisioned or is suspended")
    if user.rank <= get_settings().privileged_max_rank and not has_mfa(verified.claims):
        raise HTTPException(status_code=403, detail="MFA is required for privileged accounts")
    token_session = _track_token_session(db, user, verified)
    return Principal(user, verified.claims, token_session)


def resource_registry_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Principal:
    settings = get_settings()
    allowed_subjects = settings.trusted_resource_registry_subjects
    if not settings.resource_registry_audience or not allowed_subjects:
        raise HTTPException(status_code=503, detail="Trusted resource registry is not configured")
    try:
        verified = verify_bearer(
            _bearer_token(credentials), audience=settings.resource_registry_audience
        )
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="Invalid registry token", headers={"WWW-Authenticate": "Bearer"}) from exc
    subject = verified.claims["sub"]
    if subject not in allowed_subjects:
        raise HTTPException(status_code=403, detail="Resource registry identity is not trusted")
    user = db.scalar(select(User).where(User.subject == subject, User.active.is_(True)))
    if not user or user.rank != 6:
        raise HTTPException(status_code=403, detail="Registry identity must be an active service account")
    token_session = _track_token_session(db, user, verified)
    return Principal(user, verified.claims, token_session)

def owner_only(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
    if principal.user.rank != 0:
        raise HTTPException(status_code=403, detail="Owner authorization required")
    if not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="Recent MFA authentication is required")
    return principal


class AccessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    task_id: str | None = Field(default=None, max_length=36)
    approval_id: str | None = Field(default=None, max_length=36)


class ResourcePolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    owner_subject: str = Field(min_length=1, max_length=255)
    division: str
    classification: str
    risk: str


class AdminChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    payload: dict


class ChangeSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=255)


class ChangeId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=36)


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
    action: str
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=255)
    task_id: str = Field(min_length=1, max_length=36)



ADMIN_CHANGE_MODELS = {
    "provision_user": ProvisionUser,
    "suspend_user": ChangeSubject,
    "update_user": UpdateUser,
    "assign_task": TaskAssignmentInput,
    "share_resource": ResourceShareInput,
    "revoke_task": ChangeId,
    "revoke_share": ChangeId,
}


def canonical_admin_payload(db: Session, operation: str, payload: dict) -> dict:
    model = ADMIN_CHANGE_MODELS.get(operation)
    if model is None or not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Unsupported administrative change")
    try:
        if operation == "update_user":
            if set(payload) != {"subject", "changes"} or not isinstance(payload.get("changes"), dict):
                raise ValueError("update_user needs subject and changes")
            subject = payload["subject"]
            if not isinstance(subject, str) or not subject:
                raise ValueError("missing subject")
            parsed = model.model_validate(payload["changes"])
            changes = parsed.model_dump(mode="json", exclude_unset=True)
            if not changes or all(value is None for value in changes.values()):
                raise ValueError("empty changes")
            normalized = {"subject": subject, "changes": changes}
        else:
            parsed = model.model_validate(payload)
            normalized = parsed.model_dump(mode="json")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid administrative change payload") from exc

    if operation == "provision_user":
        normalized["divisions"] = sorted(set(normalized["divisions"]))
        if any(value not in DIVISIONS for value in normalized["divisions"]):
            raise HTTPException(status_code=422, detail="Unknown division")
        if db.scalar(select(User.id).where(User.subject == normalized["subject"])):
            raise HTTPException(status_code=409, detail="Identity already provisioned")
    elif operation == "suspend_user":
        target = db.scalar(select(User).where(User.subject == normalized["subject"]))
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.rank == 0:
            raise HTTPException(status_code=409, detail="The Owner account cannot be suspended")
    elif operation == "update_user":
        target = db.scalar(select(User).where(User.subject == normalized["subject"]))
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.rank == 0:
            raise HTTPException(status_code=409, detail="The Owner account cannot be changed")
        values = normalized["changes"]
        if values.get("divisions") is not None:
            values["divisions"] = sorted(set(values["divisions"]))
        if values.get("divisions") is not None and any(value not in DIVISIONS for value in values["divisions"]):
            raise HTTPException(status_code=422, detail="Unknown division")
        if values.get("rank") == 0:
            raise HTTPException(status_code=422, detail="The Owner rank is reserved")
    elif operation == "assign_task":
        if normalized["division"] not in DIVISIONS or not set(normalized["permissions"]) <= PERMISSIONS:
            raise HTTPException(status_code=422, detail="Unknown division or permission")
        expires = parsed.expires_at
        if expires.tzinfo is None or expires <= utcnow() or expires > utcnow() + timedelta(days=365):
            raise HTTPException(status_code=422, detail="Task expiry must be timezone-aware and within one year")
        target = db.scalar(select(User).where(User.subject == normalized["subject"], User.active.is_(True)))
        membership = db.scalar(select(DivisionMembership.id).where(
            DivisionMembership.subject == normalized["subject"],
            DivisionMembership.division == normalized["division"],
        ))
        if not target or (target.rank != 0 and not membership):
            raise HTTPException(status_code=404, detail="Active division member not found")
        normalized["permissions"] = sorted(set(normalized["permissions"]))
    elif operation == "share_resource":
        target = db.scalar(select(User).where(User.subject == normalized["subject"], User.active.is_(True)))
        resource = db.get(ResourcePolicy, (normalized["resource_type"], normalized["resource_id"]))
        if not target or not resource:
            raise HTTPException(status_code=404, detail="Active user or registered resource not found")
        if normalized["permission"] != "read":
            raise HTTPException(status_code=422, detail="Explicit resource shares are read-only")
        expires = parsed.expires_at
        if expires and (expires.tzinfo is None or expires <= utcnow()):
            raise HTTPException(status_code=422, detail="Share expiry must be a future timezone-aware timestamp")
    elif operation == "revoke_task":
        if not db.get(TaskAssignment, normalized["id"]):
            raise HTTPException(status_code=404, detail="Task assignment not found")
    elif operation == "revoke_share":
        if not db.get(SharedResourceGrant, normalized["id"]):
            raise HTTPException(status_code=404, detail="Resource share not found")
    return normalized


def payload_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _affected_subject(db: Session, change: AdminChange) -> str | None:
    payload = change.payload
    if change.operation_type in {"provision_user", "suspend_user", "update_user", "assign_task", "share_resource"}:
        return payload.get("subject")
    if change.operation_type == "revoke_task":
        task = db.get(TaskAssignment, payload.get("id"))
        return task.subject if task else None
    if change.operation_type == "revoke_share":
        grant = db.get(SharedResourceGrant, payload.get("id"))
        return grant.subject if grant else None
    return None


def consume_admin_change(db: Session, principal: Principal, change_id: str, operation: str, payload: dict) -> AdminChange:
    change = db.get(AdminChange, change_id)
    if (
        not change
        or change.requester != principal.user.subject
        or change.operation_type != operation
        or change.payload != payload
        or change.payload_hash != payload_digest(payload)
        or change.required_approver_rank != 1
    ):
        raise HTTPException(status_code=403, detail="A matching approved administrative change is required")
    approver_is_active = select(User.subject).where(
        User.subject == AdminChange.approver,
        User.active.is_(True),
        User.rank == 1,
    ).exists()
    now = utcnow()
    result = db.execute(update(AdminChange).where(
        AdminChange.id == change_id,
        AdminChange.requester == principal.user.subject,
        AdminChange.operation_type == operation,
        AdminChange.payload_hash == payload_digest(payload),
        AdminChange.status == "approved",
        AdminChange.required_approver_rank == 1,
        AdminChange.consumed_at.is_(None),
        AdminChange.expires_at > now,
        AdminChange.decided_at.is_not(None),
        AdminChange.approver.is_not(None),
        AdminChange.approver != principal.user.subject,
        approver_is_active,
    ).values(consumed_at=now))
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="Administrative approval is expired, revoked, or already consumed")
    append_audit(db, principal.user.subject, "admin_change.consumed", "success", {
        "change_id": change_id, "operation": operation, "payload_hash": change.payload_hash,
    })
    return change


def _require_reviewer(principal: Principal) -> None:
    if principal.user.rank != 1 or not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="An active Rank 1 reviewer with recent MFA is required")


def _require_action_approver(principal: Principal, required_rank: int) -> None:
    if principal.user.rank != required_rank or not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="An eligible independent approver with recent MFA is required")


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
    if principal.user.rank <= get_settings().privileged_max_rank and not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="Recent MFA authentication is required")
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
    request = AccessRequest(
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        task_id=body.task_id,
        approval_id=body.approval_id,
        environment=get_settings().environment,
    )
    decision = authorize(db, principal.user, principal.claims, request)
    allowed, reason = decision.allowed, decision.reason
    context = decision.context
    if allowed and context and requires_independent_approval(request, context):
        allowed = consume_approval(db, principal.user.subject, principal.user.rank, request, context)
        if not allowed:
            reason = "approval_expired_revoked_or_consumed"
    detail = {
        "action": body.action, "resource_type": body.resource_type,
        "resource_id": body.resource_id, "reason": reason,
    }
    if context:
        detail.update({
            "division": context.division, "classification": context.classification,
            "risk": context.risk, "resource_owner_subject": context.resource_owner_subject,
            "resource_version": context.version,
        })
    append_audit(db, principal.user.subject, "access.check", "allow" if allowed else "deny", detail)
    db.commit()
    return {"allowed": allowed, "reason": reason}



@app.post("/v1/admin/users", status_code=201)
def provision_user(
    body: ProvisionUser,
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "provision_user", body.model_dump(mode="json"))
    consume_admin_change(db, principal, change_id, "provision_user", payload)
    user = User(subject=body.subject, rank=body.rank, active=True, created_by=principal.user.subject)
    db.add(user)
    db.flush()
    for division in sorted(set(body.divisions)):
        db.add(DivisionMembership(subject=body.subject, division=division, assigned_by=principal.user.subject))
    append_audit(db, principal.user.subject, "user.provisioned", "success", {
        "subject": body.subject, "rank": body.rank, "divisions": sorted(set(body.divisions)),
    })
    db.commit()
    return {"subject": user.subject, "rank": user.rank, "active": user.active}



@app.post("/v1/admin/users/{subject}/suspend", status_code=204)
def suspend_user(
    subject: str,
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "suspend_user", {"subject": subject})
    consume_admin_change(db, principal, change_id, "suspend_user", payload)
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
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    from entity_auth.db import DivisionMembership
    payload = canonical_admin_payload(db, "update_user", {
        "subject": subject, "changes": body.model_dump(mode="json", exclude_unset=True),
    })
    consume_admin_change(db, principal, change_id, "update_user", payload)
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
    append_audit(db, principal.user.subject, "user.access_updated", "success", {
        "subject": subject, "changes": changes,
    })
    db.commit()
    return {"subject": user.subject, "rank": user.rank, "active": user.active, "changed": bool(changes)}



@app.post("/v1/admin/tasks", status_code=201)
def assign_task(
    body: TaskAssignmentInput,
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "assign_task", body.model_dump(mode="json"))
    consume_admin_change(db, principal, change_id, "assign_task", payload)
    task = TaskAssignment(
        subject=body.subject, division=body.division, description=body.description,
        permissions=sorted(set(body.permissions)), resource_type=body.resource_type,
        resource_id=body.resource_id, expires_at=body.expires_at,
        assigned_by=principal.user.subject,
    )
    db.add(task)
    db.flush()
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
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "share_resource", body.model_dump(mode="json"))
    consume_admin_change(db, principal, change_id, "share_resource", payload)
    grant_id = db.scalar(
        insert(SharedResourceGrant)
        .values(
            id=str(uuid4()), subject=body.subject, resource_type=body.resource_type,
            resource_id=body.resource_id, permission=body.permission,
            granted_by=principal.user.subject, expires_at=body.expires_at, revoked_at=None,
        )
        .on_conflict_do_update(
            index_elements=[
                SharedResourceGrant.subject, SharedResourceGrant.resource_type,
                SharedResourceGrant.resource_id, SharedResourceGrant.permission,
            ],
            set_={
                "granted_by": principal.user.subject, "expires_at": body.expires_at,
                "revoked_at": None,
            },
        )
        .returning(SharedResourceGrant.id)
    )
    append_audit(db, principal.user.subject, "resource.shared", "success", {
        "share_id": grant_id, "subject": body.subject,
        "resource_type": body.resource_type, "resource_id": body.resource_id,
        "permission": body.permission, "expires_at": body.expires_at.isoformat() if body.expires_at else None,
    })
    db.commit()
    return {"share_id": grant_id, "subject": body.subject, "permission": body.permission}



@app.post("/v1/admin/tasks/{task_id}/revoke", status_code=204)
def revoke_task(
    task_id: str,
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "revoke_task", {"id": task_id})
    consume_admin_change(db, principal, change_id, "revoke_task", payload)
    task = db.get(TaskAssignment, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task assignment not found")
    if not task.revoked_at:
        task.revoked_at = utcnow()
        outcome = "success"
    else:
        outcome = "already_revoked"
    append_audit(db, principal.user.subject, "task.revoked", outcome, {"task_id": task_id})
    db.commit()



@app.post("/v1/admin/resources/shares/{share_id}/revoke", status_code=204)
def revoke_share(
    share_id: str,
    change_id: str,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, "revoke_share", {"id": share_id})
    consume_admin_change(db, principal, change_id, "revoke_share", payload)
    share = db.get(SharedResourceGrant, share_id)
    if not share:
        raise HTTPException(status_code=404, detail="Resource share not found")
    if not share.revoked_at:
        share.revoked_at = utcnow()
        outcome = "success"
    else:
        outcome = "already_revoked"
    append_audit(db, principal.user.subject, "resource.share_revoked", outcome, {"share_id": share_id})
    db.commit()



@app.post("/v1/approvals", status_code=201)
def request_approval(
    body: ApprovalRequest,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    if principal.user.rank > 4:
        raise HTTPException(status_code=403, detail="Rank is not eligible to request operational approval")
    request = AccessRequest(
        action=body.action, resource_type=body.resource_type, resource_id=body.resource_id,
        environment=get_settings().environment, task_id=body.task_id,
    )
    scope = authorize(db, principal.user, principal.claims, request, require_independent_approval=False)
    if (
        not scope.allowed or not scope.context
        or not requires_independent_approval(request, scope.context)
    ):
        raise HTTPException(status_code=403, detail="Only scoped high-impact actions can request approval")
    required_rank = 1 if principal.user.rank == 0 else 0
    approval = ActionApproval(
        requester=principal.user.subject, division=scope.context.division, action=body.action,
        resource_type=body.resource_type, resource_id=body.resource_id,
        classification=scope.context.classification, risk=scope.context.risk,
        environment=request.environment, task_id=body.task_id,
        resource_owner_subject=scope.context.resource_owner_subject,
        resource_version=scope.context.version,
        required_approver_rank=required_rank,
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(approval)
    db.flush()
    append_audit(db, principal.user.subject, "approval.requested", "pending", {
        "approval_id": approval.id, "division": scope.context.division, "action": body.action,
        "resource_type": body.resource_type, "resource_id": body.resource_id,
        "classification": scope.context.classification, "risk": scope.context.risk,
        "environment": request.environment, "task_id": body.task_id,
        "required_approver_rank": required_rank, "resource_version": scope.context.version,
    })
    db.commit()
    return {"approval_id": approval.id, "status": approval.status, "expires_at": approval.expires_at}



@app.get("/v1/approvals/pending")
def pending_approvals(
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    if principal.user.rank not in {0, 1} or not has_recent_step_up(principal.claims):
        raise HTTPException(status_code=403, detail="An eligible approver with recent MFA is required")
    now = utcnow()
    items = db.scalars(select(ActionApproval).where(
        ActionApproval.status == "pending", ActionApproval.expires_at > now,
        ActionApproval.requester != principal.user.subject,
        ActionApproval.required_approver_rank == principal.user.rank,
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
    _require_action_approver(principal, approval.required_approver_rank)
    reviewer_is_active = select(User.subject).where(
        User.subject == principal.user.subject, User.active.is_(True),
        User.rank == approval.required_approver_rank,
    ).exists()
    result = db.execute(update(ActionApproval).where(
        ActionApproval.id == approval_id, ActionApproval.status == "pending",
        ActionApproval.expires_at > now, ActionApproval.requester != principal.user.subject,
        ActionApproval.required_approver_rank == principal.user.rank, reviewer_is_active,
    ).values(status="approved", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval was already decided or reviewer is no longer eligible")
    append_audit(db, principal.user.subject, "approval.decided", "approved", {
        "approval_id": approval_id, "requester": approval.requester,
    })
    db.commit()
    return {"approval_id": approval_id, "status": "approved"}



@app.post("/v1/approvals/{approval_id}/reject")
def reject_approval(
    approval_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    approval = db.get(ActionApproval, approval_id)
    now = utcnow()
    if not approval or approval.status != "pending" or approval.expires_at <= now:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    if approval.requester == principal.user.subject:
        raise HTTPException(status_code=403, detail="Requester cannot decide their own request")
    _require_action_approver(principal, approval.required_approver_rank)
    reviewer_is_active = select(User.subject).where(
        User.subject == principal.user.subject, User.active.is_(True),
        User.rank == approval.required_approver_rank,
    ).exists()
    result = db.execute(update(ActionApproval).where(
        ActionApproval.id == approval_id, ActionApproval.status == "pending",
        ActionApproval.expires_at > now, ActionApproval.requester != principal.user.subject,
        ActionApproval.required_approver_rank == principal.user.rank, reviewer_is_active,
    ).values(status="rejected", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval was already decided or reviewer is no longer eligible")
    append_audit(db, principal.user.subject, "approval.decided", "rejected", {
        "approval_id": approval_id, "requester": approval.requester,
    })
    db.commit()
    return {"approval_id": approval_id, "status": "rejected"}



@app.put("/v1/internal/resource-policies")
def upsert_resource_policy(
    body: ResourcePolicyInput,
    principal: Annotated[Principal, Depends(resource_registry_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    if body.division not in DIVISIONS or body.classification not in CLASSIFICATIONS or body.risk not in RISK_LEVELS:
        raise HTTPException(status_code=422, detail="Invalid server resource policy")
    owner = db.scalar(select(User).where(User.subject == body.owner_subject, User.active.is_(True)))
    if not owner or owner.rank == 6:
        raise HTTPException(status_code=422, detail="Resource owner must be an active non-service identity")
    now = utcnow()
    version = db.scalar(
        insert(ResourcePolicy)
        .values(
            resource_type=body.resource_type, resource_id=body.resource_id,
            owner_subject=body.owner_subject, division=body.division,
            classification=body.classification, risk=body.risk, version=1,
            updated_by=principal.user.subject, updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[ResourcePolicy.resource_type, ResourcePolicy.resource_id],
            set_={
                "owner_subject": body.owner_subject, "division": body.division,
                "classification": body.classification, "risk": body.risk,
                "version": ResourcePolicy.version + 1, "updated_by": principal.user.subject,
                "updated_at": now,
            },
        )
        .returning(ResourcePolicy.version)
    )
    append_audit(db, principal.user.subject, "resource.policy_updated", "success", {
        "resource_type": body.resource_type, "resource_id": body.resource_id,
        "owner_subject": body.owner_subject, "division": body.division,
        "classification": body.classification, "risk": body.risk, "version": version,
    })
    db.commit()
    return {"resource_type": body.resource_type, "resource_id": body.resource_id, "version": version}


@app.post("/v1/admin/changes", status_code=201)
def request_admin_change(
    body: AdminChangeRequest,
    principal: Annotated[Principal, Depends(owner_only)],
    db: Annotated[Session, Depends(get_db)],
):
    payload = canonical_admin_payload(db, body.operation, body.payload)
    change = AdminChange(
        requester=principal.user.subject, operation_type=body.operation, payload=payload,
        payload_hash=payload_digest(payload), required_approver_rank=1,
        status="pending", expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(change)
    db.flush()
    append_audit(db, principal.user.subject, "admin_change.requested", "pending", {
        "change_id": change.id, "operation": body.operation, "payload_hash": change.payload_hash,
    })
    db.commit()
    return {"change_id": change.id, "operation": change.operation_type, "status": change.status, "expires_at": change.expires_at}


@app.get("/v1/admin/changes/pending")
def pending_admin_changes(
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_reviewer(principal)
    now = utcnow()
    changes = db.scalars(select(AdminChange).where(
        AdminChange.status == "pending", AdminChange.expires_at > now,
        AdminChange.requester != principal.user.subject,
    ).order_by(AdminChange.created_at.asc())).all()
    return [{
        "change_id": change.id, "requester": change.requester, "operation": change.operation_type,
        "payload": change.payload, "created_at": change.created_at, "expires_at": change.expires_at,
    } for change in changes]


@app.post("/v1/admin/changes/{change_id}/approve")
def approve_admin_change(
    change_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_reviewer(principal)
    change = db.get(AdminChange, change_id)
    now = utcnow()
    if not change or change.status != "pending" or change.expires_at <= now:
        raise HTTPException(status_code=404, detail="Pending administrative change not found")
    if change.requester == principal.user.subject or _affected_subject(db, change) == principal.user.subject:
        raise HTTPException(status_code=403, detail="Requester or affected user cannot approve this change")
    reviewer_is_active = select(User.subject).where(
        User.subject == principal.user.subject, User.active.is_(True), User.rank == 1,
    ).exists()
    result = db.execute(update(AdminChange).where(
        AdminChange.id == change_id, AdminChange.status == "pending",
        AdminChange.expires_at > now, AdminChange.requester != principal.user.subject,
        reviewer_is_active,
    ).values(status="approved", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Administrative change was already decided")
    append_audit(db, principal.user.subject, "admin_change.decided", "approved", {
        "change_id": change_id, "requester": change.requester, "operation": change.operation_type,
    })
    db.commit()
    return {"change_id": change_id, "status": "approved"}


@app.post("/v1/admin/changes/{change_id}/reject")
def reject_admin_change(
    change_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_reviewer(principal)
    change = db.get(AdminChange, change_id)
    now = utcnow()
    if not change or change.status != "pending" or change.expires_at <= now:
        raise HTTPException(status_code=404, detail="Pending administrative change not found")
    if change.requester == principal.user.subject or _affected_subject(db, change) == principal.user.subject:
        raise HTTPException(status_code=403, detail="Requester or affected user cannot reject this change")
    reviewer_is_active = select(User.subject).where(
        User.subject == principal.user.subject, User.active.is_(True), User.rank == 1,
    ).exists()
    result = db.execute(update(AdminChange).where(
        AdminChange.id == change_id, AdminChange.status == "pending",
        AdminChange.expires_at > now, AdminChange.requester != principal.user.subject,
        reviewer_is_active,
    ).values(status="rejected", approver=principal.user.subject, decided_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Administrative change was already decided")
    append_audit(db, principal.user.subject, "admin_change.decided", "rejected", {
        "change_id": change_id, "requester": change.requester, "operation": change.operation_type,
    })
    db.commit()
    return {"change_id": change_id, "status": "rejected"}


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
