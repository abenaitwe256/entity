from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from entity_auth.bootstrap_owner import provision_initial_owner
from entity_auth.db import (
    ActionApproval, DivisionMembership, SessionLocal, TaskAssignment, User, utcnow,
)
from entity_auth.policy import AccessRequest, authorize


def add_user(db: Session, subject: str, rank: int, division: str | None = None, active: bool = True) -> User:
    user = User(subject=subject, rank=rank, active=active)
    db.add(user)
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
