from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import select

from entity_auth.config import get_settings
from entity_auth.bootstrap_owner import (
    provision_initial_owner, provision_initial_reviewer, provision_initial_users,
)
from entity_auth.db import (
    ActionApproval, AdminChange, AuditEvent, DivisionMembership, ResourcePolicy, SessionLocal,
    SharedResourceGrant, TaskAssignment, User, utcnow,
)
from entity_auth.main import (
    AccessCheck, ApprovalRequest, Principal, ResourcePolicyInput, access_check, app, append_audit,
    current_principal, decide_approval, get_db, request_approval, resource_registry_principal,
    revoke_session, upsert_resource_policy, verify_audit_chain,
)
from entity_auth.oidc import VerifiedToken
from entity_auth.policy import AccessRequest, authorize, consume_approval
from entity_auth.main import payload_digest


def add_user(db, subject, rank, division=None, active=True):
    user = User(subject=subject, rank=rank, active=active, created_by="test")
    db.add(user)
    db.flush()
    if division:
        db.add(DivisionMembership(subject=subject, division=division, assigned_by="test"))
        db.flush()
    return user


def add_policy(db, owner, *, resource_id="sample-1", division="science",
               classification="public", risk="low", version=1):
    policy = ResourcePolicy(
        resource_type="dataset", resource_id=resource_id, owner_subject=owner.subject,
        division=division, classification=classification, risk=risk, version=version,
        updated_by="trusted-registry",
    )
    db.add(policy)
    db.flush()
    return policy


def make_task(db, subject, division, action, *, resource_type="dataset",
              resource_id="sample-1", expires_at=None):
    task = TaskAssignment(
        subject=subject, division=division, description="scoped test task",
        permissions=[action], resource_type=resource_type, resource_id=resource_id,
        starts_at=utcnow() - timedelta(minutes=1),
        expires_at=expires_at or utcnow() + timedelta(hours=1), assigned_by="owner-sub",
    )
    db.add(task)
    db.flush()
    return task


def fresh_mfa():
    return {"sub": "test-sub", "amr": ["mfa"], "auth_time": utcnow().timestamp()}


def stale_mfa():
    return {
        "sub": "test-sub", "amr": ["mfa"],
        "auth_time": (utcnow() - timedelta(hours=1)).timestamp(),
    }


def api_as(db, user, claims, method, path, **kwargs):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_principal] = lambda: Principal(user, claims, None)
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def admin_change(db, owner, reviewer, operation, payload):
    requested = api_as(
        db, owner, fresh_mfa(), "post", "/v1/admin/changes",
        json={"operation": operation, "payload": payload},
    )
    assert requested.status_code == 201, requested.text
    change_id = requested.json()["change_id"]
    approved = api_as(
        db, reviewer, fresh_mfa(), "post", f"/v1/admin/changes/{change_id}/approve",
    )
    assert approved.status_code == 200, approved.text
    return change_id


def access_request(*, action="read", resource_id="sample-1", task_id=None, approval_id=None):
    return AccessRequest(
        action=action, resource_type="dataset", resource_id=resource_id,
        environment="development", task_id=task_id, approval_id=approval_id,
    )


def test_unknown_resource_is_denied_by_default():
    with SessionLocal() as db:
        guest = add_user(db, "guest-sub", 6)
        decision = authorize(db, guest, {}, access_request())
        assert not decision.allowed
        assert decision.reason == "resource_not_registered"
        assert decision.context is None


def test_access_request_rejects_client_supplied_risk_classification_and_ownership():
    with SessionLocal() as db:
        user = add_user(db, "guest-sub", 6)
        response = api_as(
            db, user, {}, "post", "/v1/access/check",
            json={
                "action": "read", "resource_type": "dataset", "resource_id": "sample-1",
                "division": "science", "risk": "low", "classification": "public",
                "owner_subject": "guest-sub",
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"]


def test_server_policy_cannot_be_downgraded_by_requester():
    with SessionLocal() as db:
        owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        add_policy(db, owner, risk="critical", classification="highly_restricted")
        task = make_task(db, operator.subject, "science", "read")
        decision = authorize(db, operator, fresh_mfa(), access_request(task_id=task.id))
        assert not decision.allowed
        assert decision.reason == "independent_approval_required"
        assert decision.context.risk == "critical"
        assert decision.context.classification == "highly_restricted"
        assert decision.context.resource_owner_subject == owner.subject


def test_cross_division_membership_and_task_do_not_authorize_resource():
    with SessionLocal() as db:
        owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 4, "engineering")
        add_policy(db, owner, division="science")
        task = make_task(db, operator.subject, "engineering", "read")
        decision = authorize(db, operator, fresh_mfa(), access_request(task_id=task.id))
        assert not decision.allowed
        assert decision.reason == "division_membership_required"



def test_only_allowlisted_registry_workload_can_write_server_policy(monkeypatch):
    with SessionLocal() as db:
        original_settings = get_settings()
        settings = SimpleNamespace(
            resource_registry_audience="entity-registry",
            trusted_resource_registry_subjects=frozenset({"registry-sub"}),
            audit_hmac_key=original_settings.audit_hmac_key,
        )
        monkeypatch.setattr("entity_auth.main.get_settings", lambda: settings)
        claims = {
            "sub": "attacker-sub",
            "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(utcnow().timestamp()),
            "jti": "registry-jti",
        }
        monkeypatch.setattr(
            "entity_auth.main.verify_bearer",
            lambda _token, audience=None: VerifiedToken(claims=dict(claims), token_hash="c" * 64),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")
        with pytest.raises(HTTPException) as denied:
            resource_registry_principal(credentials, db)
        assert denied.value.status_code == 403

        resource_owner = add_user(db, "resource-owner", 2)
        registry = add_user(db, "registry-sub", 6)
        claims["sub"] = registry.subject
        principal = resource_registry_principal(credentials, db)
        result = upsert_resource_policy(
            ResourcePolicyInput(
                resource_type="dataset", resource_id="sample-1",
                owner_subject=resource_owner.subject, division="science",
                classification="restricted", risk="critical",
            ),
            principal, db,
        )
        assert result["version"] == 1
        context = authorize(db, resource_owner, fresh_mfa(), access_request()).context
        assert context.resource_owner_subject == resource_owner.subject
        assert context.division == "science"
        assert context.classification == "restricted"
        assert context.risk == "critical"


def test_resource_owner_authority_is_server_derived_and_exact_resource_scoped():
    with SessionLocal() as db:
        resource_owner = add_user(db, "resource-owner", 4, "engineering")
        add_policy(db, resource_owner, division="science")
        own_resource = authorize(db, resource_owner, fresh_mfa(), access_request())
        other_resource = authorize(
            db, resource_owner, fresh_mfa(), access_request(resource_id="not-owned"),
        )
        assert own_resource.allowed
        assert own_resource.context.resource_owner_subject == resource_owner.subject
        assert not other_resource.allowed
        assert other_resource.reason == "resource_not_registered"


def test_legacy_non_read_share_cannot_grant_write_access():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        operator = add_user(db, "operator-sub", 5)
        add_policy(db, owner, classification="public", risk="low")
        db.add(SharedResourceGrant(
            subject=operator.subject, resource_type="dataset", resource_id="sample-1",
            permission="modify", granted_by=owner.subject,
        ))
        db.flush()
        decision = authorize(
            db, operator, fresh_mfa(),
            AccessRequest(
                action="modify", resource_type="dataset", resource_id="sample-1",
                environment="development",
            ),
        )
        assert not decision.allowed
        assert decision.reason == "division_membership_required"



def test_revoked_share_is_denied_and_regrant_requires_independent_approval():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        resource_owner = add_user(db, "resource-owner", 2)
        guest = add_user(db, "guest-sub", 6)
        add_policy(db, resource_owner, classification="public", risk="low")
        grant = SharedResourceGrant(
            subject=guest.subject, resource_type="dataset", resource_id="sample-1",
            permission="read", granted_by=owner.subject, revoked_at=utcnow(),
        )
        db.add(grant)
        db.flush()
        denied = authorize(db, guest, {}, access_request())
        assert not denied.allowed
        assert denied.reason == "explicit_share_required"

        body = {
            "subject": guest.subject, "resource_type": "dataset", "resource_id": "sample-1",
            "permission": "read", "expires_at": None,
        }
        change_id = admin_change(db, owner, reviewer, "share_resource", body)
        path = f"/v1/admin/resources/shares?change_id={change_id}"
        response = api_as(
            db, owner, fresh_mfa(), "post", path,
            json={"subject": guest.subject, "resource_type": "dataset",
                  "resource_id": "sample-1", "permission": "read"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["share_id"] == grant.id
        db.refresh(grant)
        assert grant.revoked_at is None
        assert authorize(db, guest, {}, access_request()).allowed

        replay = api_as(
            db, owner, fresh_mfa(), "post", path,
            json={"subject": guest.subject, "resource_type": "dataset",
                  "resource_id": "sample-1", "permission": "read"},
        )
        assert replay.status_code == 409
        assert db.scalar(select(SharedResourceGrant.id).where(
            SharedResourceGrant.subject == guest.subject,
            SharedResourceGrant.revoked_at.is_(None),
        )) == grant.id


def test_owner_change_request_requires_owner_and_recent_mfa():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        member = add_user(db, "member-sub", 2)
        payload = {"subject": "new-user", "rank": 2, "divisions": []}
        stale = api_as(
            db, owner, stale_mfa(), "post", "/v1/admin/changes",
            json={"operation": "provision_user", "payload": payload},
        )
        nonowner = api_as(
            db, member, fresh_mfa(), "post", "/v1/admin/changes",
            json={"operation": "provision_user", "payload": payload},
        )
        assert stale.status_code == 403
        assert nonowner.status_code == 403
        assert db.scalar(select(User).where(User.subject == "new-user")) is None


def test_owner_cannot_execute_admin_mutation_without_second_approval():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        path = "/v1/admin/users?change_id=unissued"
        response = api_as(
            db, owner, fresh_mfa(), "post", path,
            json={"subject": "new-user", "rank": 2, "divisions": []},
        )
        assert response.status_code in {403, 409}
        assert db.scalar(select(User).where(User.subject == "new-user")) is None


def test_owner_change_requires_independent_rank_one_approval_and_is_consumed_once():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        payload = {"subject": "new-user", "rank": 2, "divisions": ["science"]}
        requested = api_as(
            db, owner, fresh_mfa(), "post", "/v1/admin/changes",
            json={"operation": "provision_user", "payload": payload},
        )
        assert requested.status_code == 201, requested.text
        change_id = requested.json()["change_id"]

        self_approval = api_as(
            db, owner, fresh_mfa(), "post", f"/v1/admin/changes/{change_id}/approve",
        )
        assert self_approval.status_code == 403
        assert db.get(AdminChange, change_id).status == "pending"

        approved = api_as(
            db, reviewer, fresh_mfa(), "post", f"/v1/admin/changes/{change_id}/approve",
        )
        assert approved.status_code == 200, approved.text
        stale_execution = api_as(
            db, owner, stale_mfa(), "post",
            f"/v1/admin/users?change_id={change_id}", json=payload,
        )
        assert stale_execution.status_code == 403
        assert db.get(AdminChange, change_id).consumed_at is None
        executed = api_as(
            db, owner, fresh_mfa(), "post",
            f"/v1/admin/users?change_id={change_id}", json=payload,
        )
        assert executed.status_code == 201, executed.text
        change = db.get(AdminChange, change_id)
        assert change.consumed_at is not None
        assert db.scalar(select(DivisionMembership.id).where(
            DivisionMembership.subject == "new-user", DivisionMembership.division == "science",
        ))

        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "admin_change.decided"))
        assert event.actor == reviewer.subject
        assert event.detail["change_id"] == change_id



def test_rank_two_cannot_approve_owner_administration_change():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        rank_two = add_user(db, "rank-two-sub", 2)
        requested = api_as(
            db, owner, fresh_mfa(), "post", "/v1/admin/changes",
            json={
                "operation": "provision_user",
                "payload": {"subject": "new-user", "rank": 3, "divisions": []},
            },
        )
        assert requested.status_code == 201, requested.text
        change_id = requested.json()["change_id"]
        denied = api_as(
            db, rank_two, fresh_mfa(), "post",
            f"/v1/admin/changes/{change_id}/approve",
        )
        assert denied.status_code == 403
        assert db.get(AdminChange, change_id).status == "pending"
        approved = api_as(
            db, reviewer, fresh_mfa(), "post",
            f"/v1/admin/changes/{change_id}/approve",
        )
        assert approved.status_code == 200, approved.text



def test_repeated_task_revocation_consumes_approval_and_is_audited():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        member = add_user(db, "member-sub", 2, "science")
        task = make_task(db, member.subject, "science", "read")
        task.revoked_at = utcnow()
        db.flush()

        change_id = admin_change(db, owner, reviewer, "revoke_task", {"id": task.id})
        response = api_as(
            db, owner, fresh_mfa(), "post",
            f"/v1/admin/tasks/{task.id}/revoke?change_id={change_id}",
        )
        assert response.status_code == 204
        change = db.get(AdminChange, change_id)
        assert change.consumed_at is not None
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "task.revoked",
        ).order_by(AuditEvent.created_at.desc()))
        assert event.outcome == "already_revoked"
        assert event.detail["task_id"] == task.id


def test_rank_one_affected_account_cannot_approve_its_own_change():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        requested = api_as(
            db, owner, fresh_mfa(), "post", "/v1/admin/changes",
            json={
                "operation": "update_user",
                "payload": {"subject": reviewer.subject, "changes": {"active": False}},
            },
        )
        assert requested.status_code == 201, requested.text
        change_id = requested.json()["change_id"]
        denied = api_as(
            db, reviewer, fresh_mfa(), "post", f"/v1/admin/changes/{change_id}/approve",
        )
        assert denied.status_code == 403
        assert db.get(AdminChange, change_id).status == "pending"


def test_forged_admin_approval_without_decision_record_is_not_executable():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        payload = {"subject": "forged-user", "rank": 2, "divisions": []}
        change = AdminChange(
            requester=owner.subject, operation_type="provision_user", payload=payload,
            payload_hash=payload_digest(payload), required_approver_rank=1, status="approved",
            approver=reviewer.subject, expires_at=utcnow() + timedelta(minutes=10),
            decided_at=None,
        )
        db.add(change)
        db.flush()
        response = api_as(
            db, owner, fresh_mfa(), "post",
            f"/v1/admin/users?change_id={change.id}", json=payload,
        )
        assert response.status_code == 409
        assert db.scalar(select(User).where(User.subject == "forged-user")) is None


def test_admin_approval_is_bound_to_exact_payload():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        approved_payload = {"subject": "approved-user", "rank": 2, "divisions": []}
        change_id = admin_change(db, owner, reviewer, "provision_user", approved_payload)
        forged_payload = {"subject": "attacker-user", "rank": 3, "divisions": []}
        response = api_as(
            db, owner, fresh_mfa(), "post",
            f"/v1/admin/users?change_id={change_id}", json=forged_payload,
        )
        assert response.status_code == 403
        assert db.scalar(select(User).where(User.subject == "attacker-user")) is None
        assert db.scalar(select(User).where(User.subject == "approved-user")) is None


def test_non_owner_cannot_change_accounts_even_with_a_forged_change_id():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        rank_one = add_user(db, "reviewer-sub", 1)
        response = api_as(
            db, rank_one, fresh_mfa(), "post",
            "/v1/admin/users?change_id=anything",
            json={"subject": "attacker-sub", "rank": 2, "divisions": []},
        )
        assert response.status_code == 403
        assert db.scalar(select(User).where(User.subject == "attacker-sub")) is None


def test_task_and_approval_generated_ids_are_audited():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        member = add_user(db, "member-sub", 2, "science")
        task_body = {
            "subject": member.subject, "division": "science", "description": "review data",
            "permissions": ["read"], "resource_type": "dataset", "resource_id": "sample-1",
            "expires_at": (utcnow() + timedelta(hours=1)).isoformat(),
        }
        add_policy(db, owner, risk="critical", classification="restricted")
        change_id = admin_change(db, owner, reviewer, "assign_task", task_body)
        task_response = api_as(
            db, owner, fresh_mfa(), "post", f"/v1/admin/tasks?change_id={change_id}",
            json=task_body,
        )
        assert task_response.status_code == 201, task_response.text
        task_id = task_response.json()["task_id"]
        task_event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "task.assigned"))
        assert task_event.detail["task_id"] == task_id

        approval = request_approval(
            ApprovalRequest(
                action="read", resource_type="dataset", resource_id="sample-1", task_id=task_id,
            ),
            Principal(member, fresh_mfa(), None), db,
        )
        approval_event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "approval.requested",
        ).order_by(AuditEvent.created_at.desc()))
        assert approval["approval_id"]
        assert approval_event.detail["approval_id"] == approval["approval_id"]


def test_high_risk_approval_is_independent_bound_and_consumed_once():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        resource_owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        add_policy(db, resource_owner, risk="critical", classification="restricted")
        task = make_task(db, operator.subject, "science", "read")

        request_body = ApprovalRequest(
            action="read", resource_type="dataset", resource_id="sample-1", task_id=task.id,
        )
        approval = request_approval(request_body, Principal(operator, fresh_mfa(), None), db)
        record = db.get(ActionApproval, approval["approval_id"])
        assert record.required_approver_rank == 0

        with pytest.raises(HTTPException) as self_approval:
            decide_approval(record.id, Principal(operator, fresh_mfa(), None), db)
        assert self_approval.value.status_code == 403

        with pytest.raises(HTTPException) as wrong_approver:
            decide_approval(record.id, Principal(add_user(db, "reviewer-sub", 1), fresh_mfa(), None), db)
        assert wrong_approver.value.status_code == 403

        decision = decide_approval(record.id, Principal(owner, fresh_mfa(), None), db)
        assert decision["status"] == "approved"
        body = AccessCheck(
            action="read", resource_type="dataset", resource_id="sample-1",
            task_id=task.id, approval_id=record.id,
        )
        allowed = access_check(body, Principal(operator, fresh_mfa(), None), db)
        assert allowed["allowed"]
        assert record.consumed_at is not None
        replay = access_check(body, Principal(operator, fresh_mfa(), None), db)
        assert not replay["allowed"]


def test_owner_high_risk_action_requires_fresh_mfa_task_and_rank_one_approver():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        resource_owner = add_user(db, "resource-owner", 2)
        add_policy(db, resource_owner, risk="high", classification="restricted")
        task = make_task(db, owner.subject, "science", "read")

        stale = authorize(
            db, owner, stale_mfa(), access_request(task_id=task.id),
        )
        assert not stale.allowed
        assert stale.reason == "fresh_mfa_required"

        no_task = authorize(db, owner, fresh_mfa(), access_request())
        assert not no_task.allowed
        assert no_task.reason == "high_risk_task_assignment_required"

        request = request_approval(
            ApprovalRequest(
                action="read", resource_type="dataset", resource_id="sample-1", task_id=task.id,
            ),
            Principal(owner, fresh_mfa(), None), db,
        )
        record = db.get(ActionApproval, request["approval_id"])
        assert record.required_approver_rank == 1
        with pytest.raises(HTTPException) as self_approval:
            decide_approval(record.id, Principal(owner, fresh_mfa(), None), db)
        assert self_approval.value.status_code == 403

        decide_approval(record.id, Principal(reviewer, fresh_mfa(), None), db)
        result = access_check(
            AccessCheck(
                action="read", resource_type="dataset", resource_id="sample-1",
                task_id=task.id, approval_id=record.id,
            ),
            Principal(owner, fresh_mfa(), None), db,
        )
        assert result["allowed"]



def test_owner_cannot_bypass_high_classification_or_irreversible_action_approval():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        resource_owner = add_user(db, "resource-owner", 2)
        add_policy(
            db, resource_owner, classification="highly_restricted", risk="low",
        )
        task = make_task(db, owner.subject, "science", "read")

        no_task = authorize(db, owner, fresh_mfa(), access_request())
        assert not no_task.allowed
        assert no_task.reason == "high_risk_task_assignment_required"

        request = request_approval(
            ApprovalRequest(
                action="read", resource_type="dataset", resource_id="sample-1", task_id=task.id,
            ),
            Principal(owner, fresh_mfa(), None), db,
        )
        approval = db.get(ActionApproval, request["approval_id"])
        assert approval.risk == "low"
        assert approval.classification == "highly_restricted"
        decide_approval(approval.id, Principal(reviewer, fresh_mfa(), None), db)
        allowed = access_check(
            AccessCheck(
                action="read", resource_type="dataset", resource_id="sample-1",
                task_id=task.id, approval_id=approval.id,
            ),
            Principal(owner, fresh_mfa(), None), db,
        )
        assert allowed["allowed"]

        internal_owner = add_user(db, "second-owner-resource", 2)
        add_policy(
            db, internal_owner, resource_id="sample-2",
            classification="internal", risk="low",
        )
        admin_task = make_task(
            db, owner.subject, "science", "administer", resource_id="sample-2",
        )
        admin_request = AccessRequest(
            action="administer", resource_type="dataset", resource_id="sample-2",
            environment="development", task_id=admin_task.id,
        )
        denied_without_approval = authorize(db, owner, fresh_mfa(), admin_request)
        assert not denied_without_approval.allowed
        assert denied_without_approval.reason == "independent_approval_required"


def test_forged_action_approval_without_fresh_independent_decision_is_denied():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        resource_owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        add_policy(db, resource_owner, risk="critical", classification="restricted")
        task = make_task(db, operator.subject, "science", "read")
        forged = ActionApproval(
            requester=operator.subject, approver=owner.subject, division="science",
            action="read", resource_type="dataset", resource_id="sample-1",
            classification="restricted", risk="critical", environment="development",
            task_id=task.id, status="approved", decided_at=None,
            resource_owner_subject=resource_owner.subject, resource_version=1,
            required_approver_rank=0, expires_at=utcnow() + timedelta(minutes=10),
        )
        db.add(forged)
        db.flush()
        decision = authorize(
            db, operator, fresh_mfa(), access_request(task_id=task.id, approval_id=forged.id),
        )
        assert not decision.allowed
        assert decision.reason == "independent_approval_required"



def test_approval_consumption_rechecks_live_task_and_resource_policy():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        resource_owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        policy = add_policy(db, resource_owner, risk="critical", classification="restricted")
        task = make_task(db, operator.subject, "science", "read")
        approval = ActionApproval(
            requester=operator.subject, approver=owner.subject, division="science",
            action="read", resource_type="dataset", resource_id="sample-1",
            classification="restricted", risk="critical", environment="development",
            task_id=task.id, status="approved", decided_at=utcnow(),
            resource_owner_subject=resource_owner.subject, resource_version=policy.version,
            required_approver_rank=0, expires_at=utcnow() + timedelta(minutes=10),
        )
        db.add(approval)
        db.flush()
        request = access_request(task_id=task.id, approval_id=approval.id)
        decision = authorize(db, operator, fresh_mfa(), request)
        assert decision.allowed

        task.revoked_at = utcnow()
        db.flush()
        assert not consume_approval(
            db, operator.subject, operator.rank, request, decision.context,
        )
        task.revoked_at = None
        db.flush()
        assert consume_approval(
            db, operator.subject, operator.rank, request, decision.context,
        )
        db.refresh(approval)
        assert approval.consumed_at is not None


def test_resource_policy_version_change_invalidates_existing_approval():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        resource_owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        policy = add_policy(db, resource_owner, risk="critical", classification="restricted")
        task = make_task(db, operator.subject, "science", "read")
        approval = ActionApproval(
            requester=operator.subject, approver=owner.subject, division="science",
            action="read", resource_type="dataset", resource_id="sample-1",
            classification="restricted", risk="critical", environment="development",
            task_id=task.id, status="approved", decided_at=utcnow(),
            resource_owner_subject=resource_owner.subject, resource_version=policy.version,
            required_approver_rank=0, expires_at=utcnow() + timedelta(minutes=10),
        )
        db.add(approval)
        db.flush()
        policy.version += 1
        decision = authorize(
            db, operator, fresh_mfa(), access_request(task_id=task.id, approval_id=approval.id),
        )
        assert not decision.allowed
        assert decision.reason == "independent_approval_required"


def test_approval_request_audit_id_is_stable_and_uuid_generated():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        resource_owner = add_user(db, "resource-owner", 2)
        operator = add_user(db, "operator-sub", 3, "science")
        add_policy(db, resource_owner, risk="high")
        task = make_task(db, operator.subject, "science", "read")
        result = request_approval(
            ApprovalRequest(
                action="read", resource_type="dataset", resource_id="sample-1", task_id=task.id,
            ),
            Principal(operator, fresh_mfa(), None), db,
        )
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "approval.requested",
        ).order_by(AuditEvent.created_at.desc()))
        assert result["approval_id"] == event.detail["approval_id"]
        assert len(result["approval_id"]) == 36


def test_session_revocation_blocks_reuse_and_owner_requires_fresh_mfa(monkeypatch):
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        claims = {
            "sub": owner.subject, "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(utcnow().timestamp()), "jti": "session-token-1",
            **fresh_mfa(), "sub": owner.subject,
        }
        monkeypatch.setattr(
            "entity_auth.main.verify_bearer",
            lambda _token: VerifiedToken(claims=claims, token_hash="a" * 64),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")
        principal = current_principal(credentials, db)

        with pytest.raises(HTTPException) as stale:
            revoke_session(principal.session.id, Principal(owner, stale_mfa(), principal.session), db)
        assert stale.value.status_code == 403

        revoke_session(principal.session.id, Principal(owner, claims, principal.session), db)
        with pytest.raises(HTTPException) as revoked:
            current_principal(credentials, db)
        assert revoked.value.status_code == 401


def test_privileged_owner_cannot_authenticate_without_mfa(monkeypatch):
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        claims = {
            "sub": owner.subject, "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(utcnow().timestamp()), "jti": "no-mfa-token",
        }
        monkeypatch.setattr(
            "entity_auth.main.verify_bearer",
            lambda _token: VerifiedToken(claims=claims, token_hash="b" * 64),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")
        with pytest.raises(HTTPException) as denied:
            current_principal(credentials, db)
        assert denied.value.status_code == 403



def test_suspended_second_approver_invalidates_pending_high_risk_authorization():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        reviewer = add_user(db, "reviewer-sub", 1)
        resource_owner = add_user(db, "resource-owner", 2)
        add_policy(db, resource_owner, risk="critical", classification="restricted")
        task = make_task(db, owner.subject, "science", "read")
        approval = ActionApproval(
            requester=owner.subject, approver=reviewer.subject, division="science",
            action="read", resource_type="dataset", resource_id="sample-1",
            classification="restricted", risk="critical", environment="development",
            task_id=task.id, status="approved", decided_at=utcnow(),
            resource_owner_subject=resource_owner.subject, resource_version=1,
            required_approver_rank=1, expires_at=utcnow() + timedelta(minutes=10),
        )
        db.add(approval)
        db.flush()
        reviewer.active = False
        decision = authorize(
            db, owner, fresh_mfa(),
            access_request(task_id=task.id, approval_id=approval.id),
        )
        assert not decision.allowed
        assert decision.reason == "independent_approval_required"


def test_audit_chain_detects_modified_event():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        append_audit(db, owner.subject, "test.event", "success", {"value": 1})
        db.commit()
        assert verify_audit_chain(Principal(owner, fresh_mfa(), None), db)["valid"]
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "test.event"))
        event.detail = {"value": 2}
        db.commit()
        assert not verify_audit_chain(Principal(owner, fresh_mfa(), None), db)["valid"]


def test_initial_bootstrap_requires_a_distinct_rank_one_reviewer_and_audits_both():
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="reviewer is required"):
            provision_initial_owner(db, "owner-sub")
        assert db.scalar(select(User).where(User.subject == "owner-sub")) is None

        owner, reviewer = provision_initial_users(db, "owner-sub", "reviewer-sub")
        assert owner.rank == 0
        assert reviewer.rank == 1
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.initial_trust_established",
        ))
        assert event.detail == {
            "owner_subject": "owner-sub",
            "initial_reviewer_subject": "reviewer-sub",
        }


def test_initial_bootstrap_refuses_same_subject_or_nonempty_user_table():
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="distinct"):
            provision_initial_users(db, "same-sub", "same-sub")
        assert db.scalar(select(User)) is None
        add_user(db, "existing-sub", 0)
        with pytest.raises(ValueError, match="not empty"):
            provision_initial_users(db, "owner-sub", "reviewer-sub")


def test_existing_owner_only_database_can_bootstrap_one_independent_reviewer():
    with SessionLocal() as db:
        owner = add_user(db, "owner-sub", 0)
        add_user(db, "member-sub", 3)
        reviewer = provision_initial_reviewer(db, owner.subject, "initial-reviewer-sub")
        assert reviewer.rank == 1
        assert db.scalar(select(User).where(User.rank == 0)).subject == owner.subject
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.initial_reviewer_established",
        ))
        assert event.detail["owner_subject"] == owner.subject
        with pytest.raises(ValueError, match="already exists"):
            provision_initial_reviewer(db, owner.subject, "another-reviewer-sub")
        assert db.scalar(select(User).where(User.subject == "another-reviewer-sub")) is None
