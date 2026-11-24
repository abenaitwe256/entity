from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from entity_auth import bootstrap_owner
from entity_auth.config import get_settings
from entity_auth.db import (
    ORIGINAL_OWNER_KEY, AuditEvent, OriginalOwnerIdentity, ResourcePolicy, SessionLocal, User, utcnow,
)
from entity_auth.main import Principal, current_principal, owner_only, verify_audit_chain
from entity_auth.oidc import VerifiedToken
from entity_auth.policy import AccessRequest, DIVISIONS, authorize, original_owner_identity_id
from entity_auth.main import canonical_admin_payload


OWNER_SUBJECT = "owner-sub"
REVIEWER_SUBJECT = "reviewer-sub"


def identity_claims(subject, *, amr=None, auth_time=None, **extra):
    now = utcnow()
    return {
        "sub": subject,
        "iss": get_settings().oidc_issuer,
        "aud": get_settings().oidc_audience,
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iat": int(now.timestamp()),
        "jti": f"bootstrap-{subject}",
        "amr": ["mfa"] if amr is None else amr,
        "auth_time": now.timestamp() if auth_time is None else auth_time,
        **extra,
    }


def token_for(claims):
    return VerifiedToken(
        claims=claims,
        token_hash=sha256(claims["sub"].encode()).hexdigest(),
    )


def install_bootstrap_tokens(monkeypatch, owner_claims, reviewer_claims):
    tokens = {
        "owner-token": token_for(owner_claims),
        "reviewer-token": token_for(reviewer_claims),
    }
    monkeypatch.setattr(
        bootstrap_owner, "verify_bearer",
        lambda token: tokens[token],
    )
    monkeypatch.setattr(
        bootstrap_owner, "get_settings",
        lambda: get_settings(),
    )


def establish_owner(db, monkeypatch, owner_claims=None, reviewer_claims=None):
    install_bootstrap_tokens(
        monkeypatch,
        owner_claims or identity_claims(OWNER_SUBJECT),
        reviewer_claims or identity_claims(REVIEWER_SUBJECT),
    )
    return bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")


def test_verified_original_owner_identity_is_bound_to_exact_oidc_account_and_audited(monkeypatch):
    with SessionLocal() as db:
        identity, owner, reviewer = establish_owner(db, monkeypatch)

        assert UUID(identity.identity_id).version == 4
        assert identity.identity_key == ORIGINAL_OWNER_KEY
        assert identity.owner_user_id == owner.id
        assert identity.oidc_issuer == get_settings().oidc_issuer
        assert identity.oidc_subject == OWNER_SUBJECT
        assert owner.rank == 0 and owner.active
        assert reviewer.rank == 1 and reviewer.active

        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.original_owner_bound",
        ))
        assert event.outcome == "success"
        assert event.detail == {
            "identity_id": identity.identity_id,
            "issuer": get_settings().oidc_issuer,
            "owner_subject": OWNER_SUBJECT,
            "reviewer_subject": REVIEWER_SUBJECT,
            "binding_mode": "initial-owner",
        }
        review = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.original_owner_bootstrap.reviewed",
        ))
        assert review.actor == REVIEWER_SUBJECT
        assert review.outcome == "success"
        assert review.detail["identity_id"] == identity.identity_id
        assert verify_audit_chain(Principal(owner, identity_claims(OWNER_SUBJECT), None), db)["valid"]


def test_database_rejects_owner_anchor_for_wrong_rank_or_subject():
    with SessionLocal() as db:
        reviewer = User(
            subject=REVIEWER_SUBJECT, rank=1, active=True, created_by="controlled-test",
        )
        db.add(reviewer)
        db.commit()

        # A non-Owner account cannot receive the singleton identity anchor, even through direct SQL.
        db.add(OriginalOwnerIdentity(
            identity_key=ORIGINAL_OWNER_KEY,
            identity_id=str(uuid4()),
            owner_user_id=reviewer.id,
            oidc_issuer=get_settings().oidc_issuer,
            oidc_subject=reviewer.subject,
            created_at=utcnow(),
            created_by=OWNER_SUBJECT,
        ))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()

        # A Rank 0 row cannot be bound to a different OIDC subject.
        owner = User(subject=OWNER_SUBJECT, rank=0, active=True, created_by="controlled-test")
        db.add(owner)
        db.flush()
        db.add(OriginalOwnerIdentity(
            identity_key=ORIGINAL_OWNER_KEY,
            identity_id=str(uuid4()),
            owner_user_id=owner.id,
            oidc_issuer=get_settings().oidc_issuer,
            oidc_subject="forged-subject",
            created_at=utcnow(),
            created_by=OWNER_SUBJECT,
        ))
        with pytest.raises(DBAPIError):
            db.flush()


def test_owner_authentication_requires_the_immutable_identity_binding(monkeypatch):
    with SessionLocal() as db:
        identity, owner, _reviewer = establish_owner(db, monkeypatch)
        claims = identity_claims(OWNER_SUBJECT)
        monkeypatch.setattr("entity_auth.main.verify_bearer", lambda _token: token_for(claims))

        principal = current_principal(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="owner-token"),
            db,
        )
        assert principal.user.id == owner.id
        assert principal.original_owner_identity_id == identity.identity_id

        assert owner_only(principal, db).original_owner_identity_id == identity.identity_id


def test_unanchored_rank_zero_account_cannot_authenticate_or_authorize(monkeypatch):
    with SessionLocal() as db:
        owner = User(subject=OWNER_SUBJECT, rank=0, active=True, created_by="untrusted-test")
        db.add(owner)
        db.flush()
        claims = identity_claims(OWNER_SUBJECT)
        monkeypatch.setattr("entity_auth.main.verify_bearer", lambda _token: token_for(claims))

        with pytest.raises(HTTPException) as denied:
            current_principal(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials="owner-token"),
                db,
            )
        assert denied.value.status_code == 403

        decision = authorize(
            db,
            owner,
            claims,
            AccessRequest(
                action="read", resource_type="dataset", resource_id="owner-test",
                environment="development",
            ),
        )
        assert not decision.allowed
        assert decision.reason == "owner_identity_binding_required"


def test_name_and_country_of_birth_cannot_impersonate_or_bind_the_owner(monkeypatch):
    attacker = identity_claims(
        "attacker-sub",
        name="Abenaitwe Dickson",
        country_of_birth="Uganda",
    )
    install_bootstrap_tokens(
        monkeypatch, attacker, identity_claims(REVIEWER_SUBJECT),
    )
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="does not match the designated Owner"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")
        assert db.scalar(select(User)) is None
        assert db.scalar(select(OriginalOwnerIdentity)) is None
        assert db.scalar(select(AuditEvent)) is None


@pytest.mark.parametrize(
    "role,amr,auth_age",
    [
        ("owner", [], 0),
        ("owner", ["mfa"], 3600),
        ("reviewer", [], 0),
        ("reviewer", ["mfa"], 3600),
    ],
)
def test_bootstrap_fails_closed_without_fresh_mfa_for_both_identities(
    monkeypatch, role, amr, auth_age,
):
    owner_claims = identity_claims(OWNER_SUBJECT)
    reviewer_claims = identity_claims(REVIEWER_SUBJECT)
    target = owner_claims if role == "owner" else reviewer_claims
    target["amr"] = amr
    target["auth_time"] = (utcnow() - timedelta(seconds=auth_age)).timestamp()
    install_bootstrap_tokens(monkeypatch, owner_claims, reviewer_claims)

    with SessionLocal() as db:
        with pytest.raises(ValueError, match="fresh MFA"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")
        db.rollback()
        assert db.scalar(select(User)) is None
        assert db.scalar(select(OriginalOwnerIdentity)) is None


def test_bootstrap_rejects_an_unpinned_or_wrong_independent_reviewer(monkeypatch):
    owner_claims = identity_claims(OWNER_SUBJECT)
    unexpected_reviewer = identity_claims("unexpected-reviewer-sub")
    install_bootstrap_tokens(monkeypatch, owner_claims, unexpected_reviewer)

    with SessionLocal() as db:
        with pytest.raises(ValueError, match="pinned bootstrap reviewer"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")
        db.rollback()
        assert db.scalar(select(User)) is None
        assert db.scalar(select(OriginalOwnerIdentity)) is None

    with pytest.raises(ValueError, match="Pin ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT"):
        bootstrap_owner.verify_bootstrap_tokens(
            "owner-token", "reviewer-token",
            settings=get_settings().model_copy(
                update={"original_owner_bootstrap_reviewer_subject": None},
            ),
        )


def test_owner_privileged_check_requires_fresh_mfa(monkeypatch):
    with SessionLocal() as db:
        identity, owner, _reviewer = establish_owner(db, monkeypatch)
        claims = identity_claims(OWNER_SUBJECT, amr=[])
        principal = Principal(owner, claims, None, identity.identity_id)

        with pytest.raises(HTTPException) as denied:
            owner_only(principal, db)
        assert denied.value.status_code == 403
        assert "Recent MFA" in denied.value.detail


def test_bootstrap_replay_and_duplicate_owner_registration_are_denied(monkeypatch):
    with SessionLocal() as db:
        identity, owner, _reviewer = establish_owner(db, monkeypatch)
        db.commit()

        with pytest.raises(ValueError, match="already established"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")

        with pytest.raises(HTTPException) as rank_zero:
            canonical_admin_payload(
                db, "provision_user", {"subject": "attacker-sub", "rank": 0},
            )
        assert rank_zero.value.status_code == 422

        duplicate = User(
            subject="attacker-sub", rank=0, active=True, created_by="ordinary-role-operation",
        )
        db.add(duplicate)
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()

        assert db.scalar(select(User).where(User.rank == 0)).subject == OWNER_SUBJECT
        assert db.scalar(select(OriginalOwnerIdentity)).identity_id == identity.identity_id
        assert owner.active


def test_owner_role_changes_suspension_and_transfer_are_blocked_and_auditable(monkeypatch):
    with SessionLocal() as db:
        identity, owner, _reviewer = establish_owner(db, monkeypatch)
        db.commit()

        with pytest.raises(HTTPException) as update:
            canonical_admin_payload(
                db, "update_user",
                {"subject": OWNER_SUBJECT, "changes": {"active": False}},
            )
        assert update.value.status_code == 409

        owner.rank = 1
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
        owner = db.get(User, owner.id)
        assert owner.rank == 0 and owner.active

        identity = db.get(OriginalOwnerIdentity, ORIGINAL_OWNER_KEY)
        identity.owner_user_id = "00000000-0000-4000-8000-000000000099"
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()

        identity = db.get(OriginalOwnerIdentity, ORIGINAL_OWNER_KEY)
        db.delete(identity)
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()

        identity = db.get(OriginalOwnerIdentity, ORIGINAL_OWNER_KEY)
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.original_owner_bound",
        ))
        assert identity.identity_id == event.detail["identity_id"]


def test_existing_designated_owner_can_be_bound_once_with_two_verified_mfa_identities(monkeypatch):
    with SessionLocal() as db:
        existing_owner = User(
            subject=OWNER_SUBJECT, rank=0, active=True, created_by="legacy-bootstrap",
        )
        db.add(existing_owner)
        db.flush()
        existing_reviewer = User(
            subject=REVIEWER_SUBJECT, rank=1, active=True, created_by="legacy-bootstrap",
        )
        db.add(existing_reviewer)
        db.flush()

        identity, owner, reviewer = establish_owner(db, monkeypatch)
        assert identity.owner_user_id == existing_owner.id
        assert owner.id == existing_owner.id
        assert reviewer.id == existing_reviewer.id
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "identity.original_owner_bound",
        ))
        assert event.detail["binding_mode"] == "bind-existing-owner"


def test_resource_policy_changes_do_not_change_original_owner_identity(monkeypatch):
    with SessionLocal() as db:
        identity, owner, _reviewer = establish_owner(db, monkeypatch)
        db.add(ResourcePolicy(
            resource_type="dataset",
            resource_id="owner-policy",
            owner_subject=owner.subject,
            division="core",
            classification="internal",
            risk="low",
            version=1,
            updated_by=owner.subject,
        ))
        db.commit()

        policy = db.get(ResourcePolicy, ("dataset", "owner-policy"))
        policy.classification = "restricted"
        policy.risk = "high"
        policy.version = 2
        policy.updated_by = "policy-reviewer"
        db.commit()

        assert original_owner_identity_id(db, owner) == identity.identity_id
        assert db.get(OriginalOwnerIdentity, ORIGINAL_OWNER_KEY).identity_id == identity.identity_id
        assert owner.rank == 0 and owner.active


def test_recovery_cannot_rebind_owner_to_a_new_oidc_subject(monkeypatch):
    with SessionLocal() as db:
        identity, owner, reviewer = establish_owner(db, monkeypatch)
        db.commit()

        replacement_owner = identity_claims(
            "replacement-sub",
            name="Abenaitwe Dickson",
            country_of_birth="Uganda",
        )
        install_bootstrap_tokens(
            monkeypatch, replacement_owner, identity_claims(REVIEWER_SUBJECT),
        )
        with pytest.raises(ValueError, match="does not match the designated Owner"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")

        install_bootstrap_tokens(
            monkeypatch, identity_claims(OWNER_SUBJECT), identity_claims(REVIEWER_SUBJECT),
        )
        with pytest.raises(ValueError, match="already established"):
            bootstrap_owner.bootstrap_original_owner(db, "owner-token", "reviewer-token")

        assert db.scalar(select(OriginalOwnerIdentity)).identity_id == identity.identity_id
        assert db.scalar(select(User).where(User.rank == 0)).id == owner.id
        assert db.scalar(select(User).where(User.rank == 1)).id == reviewer.id


def test_authorization_policy_preserves_all_fourteen_divisions():
    assert DIVISIONS == {
        "mind", "reality", "human", "science", "engineering", "space", "planet", "future",
        "nano", "quantum", "reverse", "code", "evolve", "core",
    }
