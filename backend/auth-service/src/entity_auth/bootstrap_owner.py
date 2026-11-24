from __future__ import annotations

import getpass
from pathlib import Path
from uuid import uuid4

import jwt
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from entity_auth.config import Settings, get_settings
from entity_auth.db import (
    ORIGINAL_OWNER_KEY, OriginalOwnerIdentity, SessionLocal, User, utcnow,
)
from entity_auth.oidc import verify_bearer
from entity_auth.policy import has_recent_step_up


_BOOTSTRAP_ADVISORY_LOCK = 7408216302


def _verified_subject(token: str, role: str) -> str:
    if not token or not token.strip():
        raise ValueError(f"A fresh {role} OIDC token is required")
    try:
        verified = verify_bearer(token.strip())
    except (jwt.PyJWTError, ValueError, OSError):
        raise ValueError(f"The {role} OIDC token could not be verified") from None

    subject = verified.claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError(f"The {role} OIDC token has no valid subject")
    if not has_recent_step_up(verified.claims):
        raise ValueError(f"The {role} identity must complete fresh MFA before bootstrap")
    return subject


def verify_bootstrap_tokens(
    owner_token: str, reviewer_token: str, *, settings: Settings | None = None
) -> tuple[str, str]:
    """Validate both short-lived OIDC identities before any Owner record is created."""
    settings = settings or get_settings()
    expected_owner = settings.original_owner_subject
    if not expected_owner:
        raise ValueError("Pin ENTITY_ORIGINAL_OWNER_SUBJECT before bootstrap")
    owner_subject = _verified_subject(owner_token, "designated Owner")
    if owner_subject != expected_owner:
        raise ValueError("Authenticated Owner subject does not match the designated Owner binding")
    expected_reviewer = settings.original_owner_bootstrap_reviewer_subject
    if not expected_reviewer:
        raise ValueError("Pin ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT before bootstrap")
    reviewer_subject = _verified_subject(reviewer_token, "independent Rank 1 reviewer")
    if reviewer_subject != expected_reviewer:
        raise ValueError("Authenticated reviewer subject does not match the pinned bootstrap reviewer")
    if reviewer_subject == owner_subject:
        raise ValueError("The initial Owner and independent reviewer must be different identities")
    return owner_subject, reviewer_subject


def _establish_original_owner(
    db: Session,
    owner_subject: str,
    reviewer_subject: str,
    *,
    issuer: str,
) -> tuple[OriginalOwnerIdentity, User, User]:
    """Create or bind the one immutable Owner identity after token verification."""
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _BOOTSTRAP_ADVISORY_LOCK})
    if db.get(OriginalOwnerIdentity, ORIGINAL_OWNER_KEY):
        raise ValueError("Original Owner identity is already established; bootstrap cannot be replayed")

    existing_owner = db.scalar(select(User).where(User.rank == 0).with_for_update())
    designated_account = db.scalar(
        select(User).where(User.subject == owner_subject).with_for_update()
    )
    if existing_owner:
        if existing_owner.subject != owner_subject or not existing_owner.active:
            raise ValueError("Existing Rank 0 account does not match the active designated Owner")
        if designated_account is not existing_owner and (
            not designated_account or designated_account.id != existing_owner.id
        ):
            raise ValueError("Designated Owner subject is bound to a different account")
        owner = existing_owner
        binding_mode = "bind-existing-owner"
    else:
        if db.scalar(select(User.id).limit(1)):
            raise ValueError(
                "Accounts already exist without a designated Owner; operator review is required"
            )
        if designated_account:
            raise ValueError("Designated Owner subject is already provisioned at a non-Owner rank")
        owner = User(
            subject=owner_subject, rank=0, active=True,
            created_by="controlled_original_owner_bootstrap",
        )
        db.add(owner)
        db.flush()
        binding_mode = "initial-owner"

    reviewer = db.scalar(
        select(User).where(User.subject == reviewer_subject).with_for_update()
    )
    if reviewer:
        if reviewer.rank != 1 or not reviewer.active:
            raise ValueError(
                "Authenticated reviewer must be a separately provisioned active Rank 1 identity"
            )
    else:
        reviewer = User(
            subject=reviewer_subject, rank=1, active=True,
            created_by="controlled_original_owner_bootstrap",
        )
        db.add(reviewer)

    db.flush()
    identity = OriginalOwnerIdentity(
        identity_key=ORIGINAL_OWNER_KEY,
        identity_id=str(uuid4()),
        owner_user_id=owner.id,
        oidc_issuer=issuer,
        oidc_subject=owner_subject,
        created_at=utcnow(),
        created_by=owner_subject,
    )
    db.add(identity)
    db.flush()

    # Bind the OIDC subject and account in the same HMAC-audited transaction.
    from entity_auth.main import append_audit

    append_audit(db, reviewer_subject, "identity.original_owner_bootstrap.reviewed", "success", {
        "identity_id": identity.identity_id,
        "issuer": issuer,
        "owner_subject": owner_subject,
        "reviewer_subject": reviewer_subject,
        "binding_mode": binding_mode,
    })
    append_audit(db, owner_subject, "identity.original_owner_bound", "success", {
        "identity_id": identity.identity_id,
        "issuer": issuer,
        "owner_subject": owner_subject,
        "reviewer_subject": reviewer_subject,
        "binding_mode": binding_mode,
    })
    return identity, owner, reviewer


def bootstrap_original_owner(
    db: Session, owner_token: str, reviewer_token: str
) -> tuple[OriginalOwnerIdentity, User, User]:
    settings = get_settings()
    owner_subject, reviewer_subject = verify_bootstrap_tokens(
        owner_token, reviewer_token, settings=settings,
    )
    return _establish_original_owner(
        db, owner_subject, reviewer_subject, issuer=settings.oidc_issuer,
    )


def main() -> None:
    settings = get_settings()
    if not settings.original_owner_subject:
        raise SystemExit("Pin ENTITY_ORIGINAL_OWNER_SUBJECT before bootstrap")

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parent / "migrations")
    )
    command.upgrade(config, "head")

    # getpass keeps short-lived bearer tokens out of argv, shell history and normal echo.
    owner_token = getpass.getpass("Fresh-MFA OIDC access token for the designated Owner: ")
    reviewer_token = getpass.getpass("Fresh-MFA OIDC access token for an independent Rank 1 reviewer: ")
    try:
        with SessionLocal.begin() as db:
            identity, _owner, _reviewer = bootstrap_original_owner(
                db, owner_token, reviewer_token,
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    print(
        "Original Owner identity established through verified OIDC and fresh MFA. "
        f"Internal identity ID: {identity.identity_id}"
    )


if __name__ == "__main__":
    main()
