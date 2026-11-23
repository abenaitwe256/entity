from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from entity_auth.db import SessionLocal, User


def provision_initial_users(db: Session, owner_subject: str, reviewer_subject: str) -> tuple[User, User]:
    if db.scalar(select(User).limit(1)):
        raise ValueError("Refusing initial bootstrap: the user table is not empty")
    if (
        not owner_subject or not owner_subject.strip()
        or not reviewer_subject or not reviewer_subject.strip()
        or owner_subject == reviewer_subject
    ):
        raise ValueError("Initial Owner and Rank 1 reviewer must be distinct, non-empty OIDC subjects")

    owner = User(subject=owner_subject, rank=0, active=True, created_by="bootstrap")
    reviewer = User(subject=reviewer_subject, rank=1, active=True, created_by="bootstrap")
    db.add_all([owner, reviewer])
    db.flush()

    # Bootstrap is the initial trust ceremony; record both identities in the HMAC audit chain.
    from entity_auth.main import append_audit

    append_audit(db, "bootstrap", "identity.initial_trust_established", "success", {
        "owner_subject": owner_subject,
        "initial_reviewer_subject": reviewer_subject,
    })
    return owner, reviewer


def provision_initial_reviewer(db: Session, owner_subject: str, reviewer_subject: str) -> User:
    """One-time deployment-operator bootstrap for an existing Owner-only database."""
    owner = db.scalar(select(User).where(
        User.subject == owner_subject, User.rank == 0, User.active.is_(True),
    ))
    if not owner:
        raise ValueError("The specified active Owner was not found")
    active_reviewer = db.scalar(select(User.id).where(User.rank == 1, User.active.is_(True)).limit(1))
    if active_reviewer:
        raise ValueError("An active Rank 1 reviewer already exists")
    if (
        not reviewer_subject or not reviewer_subject.strip()
        or reviewer_subject == owner_subject
        or db.scalar(select(User.id).where(User.subject == reviewer_subject))
    ):
        raise ValueError("Initial reviewer must be a distinct, not-yet-provisioned OIDC subject")

    reviewer = User(
        subject=reviewer_subject, rank=1, active=True, created_by="bootstrap",
    )
    db.add(reviewer)
    db.flush()
    from entity_auth.main import append_audit

    append_audit(db, "bootstrap", "identity.initial_reviewer_established", "success", {
        "owner_subject": owner_subject,
        "initial_reviewer_subject": reviewer_subject,
    })
    return reviewer


def provision_initial_owner(
    db: Session, subject: str, initial_reviewer_subject: str | None = None
) -> User:
    """Compatibility helper that refuses an Owner-only bootstrap with no second reviewer."""
    if initial_reviewer_subject is None:
        raise ValueError("An initial independent Rank 1 reviewer is required")
    owner, _reviewer = provision_initial_users(db, subject, initial_reviewer_subject)
    return owner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the schema and establish the initial Owner and independent reviewer."
    )
    parser.add_argument("--owner-subject", required=True, help="Exact OIDC sub claim for the Owner")
    parser.add_argument(
        "--initial-reviewer-subject", required=True,
        help="Exact, different OIDC sub claim for the initial Rank 1 reviewer",
    )
    args = parser.parse_args()

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parent / "migrations")
    )
    command.upgrade(config, "head")
    with SessionLocal.begin() as db:
        try:
            if db.scalar(select(User.id).limit(1)):
                provision_initial_reviewer(
                    db, args.owner_subject, args.initial_reviewer_subject,
                )
            else:
                provision_initial_users(
                    db, args.owner_subject, args.initial_reviewer_subject,
                )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print("Initial Owner and Rank 1 reviewer provisioned. Protect both identities with MFA.")
