from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from entity_auth.bootstrap_owner import provision_initial_owner
from entity_auth.db import (
    ActionApproval, AuditEvent, DivisionMembership, SessionLocal, SharedResourceGrant,
    TaskAssignment, User, utcnow,
)
from entity_auth.main import (
    ApprovalRequest as ApprovalRequestBody, Principal, ResourceShareInput, TaskAssignmentInput,
    app, assign_task, current_principal, get_db, owner_only, request_approval, revoke_session,
    revoke_share, share_resource,
)
from entity_auth.oidc import VerifiedToken
from entity_auth.policy import AccessRequest, authorize


def add_user(db: Session, subject: str, rank: int, division: str | None = None, active: bool = True) -> User:
    user = User(subject=subject, rank=rank, active=active)
    db.add(user)
    db.flush()
    if division:
        db.add(DivisionMembership(subject=subject, division=division))
    db.flush()
    return user


def fresh_mfa() -> dict:
    return {"amr": ["mfa"], "auth_time": datetime.now(timezone.utc).timestamp()}


def make_task(db: Session, subject: str, division: str, action: str, expires_at: datetime | None = None) -> TaskAssignment:
    task = TaskAssignment(
        subject=subject, division=division, description="test task", permissions=[action],
        resource_type="dataset", resource_id="sample-1", starts_at=utcnow() - timedelta(minutes=5),
        expires_at=expires_at or utcnow() + timedelta(hours=1), assigned_by="owner-sub",
    )
    db.add(task)
    db.flush()
    return task


def test_guest_requires_explicit_read_share():
    with SessionLocal.begin() as db:
        guest = add_user(db, "guest-sub", 6)
        denied = authorize(db, guest, {}, AccessRequest(
            division="science", action="read", resource_type="dataset", resource_id="sample-1",
            classification="public",
        ))
        assert not denied.allowed
        assert denied.reason == "explicit_share_required"


def test_division_membership_does_not_cross_divisions():
    with SessionLocal.begin() as db:
        operator = add_user(db, "operator-sub", 4, "engineering")
        task = make_task(db, operator.subject, "engineering", "read")
        decision = authorize(db, operator, fresh_mfa(), AccessRequest(
            division="science", action="read", resource_type="dataset", resource_id="sample-1",
            task_id=task.id,
        ))
        assert not decision.allowed
        assert decision.reason == "division_membership_required"


def test_expired_assignment_does_not_authorize_write():
    with SessionLocal.begin() as db:
        operator = add_user(db, "operator-sub", 4, "engineering")
        task = make_task(db, operator.subject, "engineering", "modify", utcnow() - timedelta(seconds=1))
        decision = authorize(db, operator, fresh_mfa(), AccessRequest(
            division="engineering", action="modify", resource_type="dataset", resource_id="sample-1",
            task_id=task.id,
        ))
        assert not decision.allowed


def test_suspended_user_is_denied_even_with_assignment():
    with SessionLocal.begin() as db:
        operator = add_user(db, "operator-sub", 4, "engineering", active=False)
        decision = authorize(db, operator, fresh_mfa(), AccessRequest(
            division="engineering", action="read", resource_type="dataset", resource_id="sample-1",
        ))
        assert not decision.allowed
        assert decision.reason == "account_disabled"


def test_viewer_cannot_escalate_to_create():
    with SessionLocal.begin() as db:
        viewer = add_user(db, "viewer-sub", 6, "science")
        decision = authorize(db, viewer, {}, AccessRequest(
            division="science", action="create", resource_type="dataset", resource_id="sample-1",
        ))
        assert not decision.allowed


def test_unapproved_or_self_approved_high_risk_execution_is_denied():
    with SessionLocal.begin() as db:
        owner = add_user(db, "owner-sub", 0)
        task = make_task(db, owner.subject, "engineering", "execute")
        self_approval = ActionApproval(
            requester=owner.subject, approver=owner.subject, division="engineering", action="execute",
            resource_type="dataset", resource_id="sample-1", classification="internal", risk="critical",
            environment="production", task_id=task.id, status="approved",
            expires_at=utcnow() + timedelta(hours=1), decided_at=utcnow(),
        )
        db.add(self_approval)
        db.flush()
        decision = authorize(db, owner, fresh_mfa(), AccessRequest(
            division="engineering", action="execute", resource_type="dataset", resource_id="sample-1",
            classification="internal", risk="critical", environment="production",
            task_id=task.id, approval_id=self_approval.id,
        ))
        assert not decision.allowed
        assert decision.reason == "independent_approval_required"


def test_execution_is_disabled_outside_production():
    with SessionLocal.begin() as db:
        operator = add_user(db, "operator-sub", 4, "engineering")
        task = make_task(db, operator.subject, "engineering", "execute")
        decision = authorize(db, operator, fresh_mfa(), AccessRequest(
            division="engineering", action="execute", resource_type="dataset", resource_id="sample-1",
            environment="development", task_id=task.id,
        ))
        assert not decision.allowed
        assert decision.reason == "execution_disabled_outside_production"


def test_owner_bootstrap_is_one_time_and_preserves_existing_identity():
    with SessionLocal.begin() as db:
        owner = provision_initial_owner(db, "owner-sub")
        assert owner.rank == 0
        try:
            provision_initial_owner(db, "attacker-sub")
        except ValueError as exc:
            assert "not empty" in str(exc)
        else:
            raise AssertionError("A second bootstrap must not overwrite or add an owner")



def test_approved_high_risk_execution_uses_approver_subject():
    with SessionLocal.begin() as db:
        owner = add_user(db, "owner-sub", 0)
        operator = add_user(db, "operator-sub", 4, "engineering")
        task = make_task(db, operator.subject, "engineering", "execute")
        request = AccessRequest(
            division="engineering", action="execute", resource_type="dataset",
            resource_id="sample-1", classification="internal", risk="critical",
            environment="production", task_id=task.id,
        )
        denied = authorize(db, operator, fresh_mfa(), request)
        assert not denied.allowed
        approval = ActionApproval(
            requester=operator.subject, approver=owner.subject, division="engineering",
            action="execute", resource_type="dataset", resource_id="sample-1",
            classification="internal", risk="critical", environment="production",
            task_id=task.id, status="approved", expires_at=utcnow() + timedelta(hours=1),
            decided_at=utcnow(),
        )
        db.add(approval)
        db.flush()
        request = AccessRequest(
            division="engineering", action="execute", resource_type="dataset",
            resource_id="sample-1", classification="internal", risk="critical",
            environment="production", task_id=task.id, approval_id=approval.id,
        )
        decision = authorize(db, operator, fresh_mfa(), request)
        assert decision.allowed
        assert decision.reason == "authorized"


def test_owner_only_requires_owner_and_recent_mfa():
    with SessionLocal.begin() as db:
        owner = add_user(db, "owner-sub", 0)
        member = add_user(db, "member-sub", 1)
        owner_principal = Principal(owner, fresh_mfa(), None)
        assert owner_only(owner_principal) is owner_principal
        with pytest.raises(HTTPException) as exc:
            owner_only(Principal(member, fresh_mfa(), None))
        assert exc.value.status_code == 403
        stale_claims = {
            "amr": ["mfa"],
            "auth_time": datetime.now(timezone.utc).timestamp() - 600,
        }
        with pytest.raises(HTTPException) as exc:
            owner_only(Principal(owner, stale_claims, None))
        assert exc.value.status_code == 403


def test_revoked_resource_share_can_be_regranted_and_audited():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        guest = add_user(db, "guest-sub", 6)
        principal = Principal(owner, fresh_mfa(), None)
        body = ResourceShareInput(
            subject=guest.subject, resource_type="dataset", resource_id="sample-1",
            permission="read",
        )
        first = share_resource(body, principal, db)
        revoke_share(first["share_id"], principal, db)
        restored = share_resource(body, principal, db)
        assert restored["share_id"] == first["share_id"]
        grant = db.get(SharedResourceGrant, restored["share_id"])
        assert grant is not None
        db.refresh(grant)
        assert grant.revoked_at is None
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "resource.shared").order_by(AuditEvent.created_at.desc()))
        assert event.detail["share_id"] == restored["share_id"]
        decision = authorize(db, guest, {}, AccessRequest(
            division="science", action="read", resource_type="dataset",
            resource_id="sample-1", classification="public",
        ))
        assert decision.allowed
        high_risk = authorize(db, guest, {}, AccessRequest(
            division="science", action="read", resource_type="dataset",
            resource_id="sample-1", classification="public", risk="high",
        ))
        assert not high_risk.allowed
        assert high_risk.reason == "independent_approval_required"


def test_task_audit_correlates_generated_task_id():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        member = add_user(db, "member-sub", 2, "science")
        body = TaskAssignmentInput(
            subject=member.subject, division="science", description="review dataset",
            permissions=["read"], expires_at=utcnow() + timedelta(hours=1),
        )
        result = assign_task(body, Principal(owner, fresh_mfa(), None), db)
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "task.assigned"))
        assert result["task_id"]
        assert event.detail["task_id"] == result["task_id"]


def test_approval_audit_correlates_generated_approval_id():
    with SessionLocal() as db:
        requester = add_user(db, "requester-sub", 3, "engineering")
        task = make_task(db, requester.subject, "engineering", "approve")
        body = ApprovalRequestBody(
            division="engineering", action="approve", resource_type="dataset",
            resource_id="sample-1", classification="internal", risk="critical",
            task_id=task.id,
        )
        result = request_approval(body, Principal(requester, fresh_mfa(), None), db)
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "approval.requested"))
        assert result["approval_id"]
        assert event.detail["approval_id"] == result["approval_id"]


def test_revoked_session_is_denied_on_next_request(monkeypatch):
    with SessionLocal() as db:
        user = add_user(db, "session-sub", 6)
        claims = {
            "sub": user.subject,
            "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(utcnow().timestamp()),
            "jti": "token-1",
        }
        monkeypatch.setattr(
            "entity_auth.main.verify_bearer",
            lambda _token: VerifiedToken(claims=claims, token_hash="a" * 64),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")
        principal = current_principal(credentials, db)
        revoke_session(principal.session.id, principal, db)
        with pytest.raises(HTTPException) as exc:
            current_principal(credentials, db)
        assert exc.value.status_code == 401


def test_session_hash_collision_cannot_cross_user_boundary(monkeypatch):
    with SessionLocal() as db:
        first = add_user(db, "first-sub", 6)
        second = add_user(db, "second-sub", 6)
        claims = {"sub": first.subject, "exp": int((utcnow() + timedelta(hours=1)).timestamp())}
        monkeypatch.setattr(
            "entity_auth.main.verify_bearer",
            lambda _token: VerifiedToken(claims=claims, token_hash="b" * 64),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")
        current_principal(credentials, db)
        claims["sub"] = second.subject
        with pytest.raises(HTTPException) as exc:
            current_principal(credentials, db)
        assert exc.value.status_code == 401



def test_non_owner_cannot_provision_users():
    with SessionLocal() as db:
        member = add_user(db, "member-sub", 1)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[current_principal] = lambda: Principal(member, fresh_mfa(), None)
        try:
            response = TestClient(app).post(
                "/v1/admin/users",
                json={"subject": "attacker-sub", "rank": 1, "divisions": []},
            )
            assert response.status_code == 403
            assert db.scalar(select(User).where(User.subject == "attacker-sub")) is None
        finally:
            app.dependency_overrides.clear()
