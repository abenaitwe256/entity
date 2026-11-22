from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from entity_auth.db import Base, SessionLocal, User, engine


def provision_initial_owner(db: Session, subject: str) -> User:
    if db.scalar(select(User).limit(1)):
        raise ValueError("Refusing owner bootstrap: the user table is not empty")
    owner = User(subject=subject, rank=0, active=True, created_by="bootstrap")
    db.add(owner)
    db.flush()
    return owner


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the schema and provision the single ENTITY owner.")
    parser.add_argument("--owner-subject", required=True, help="Exact OIDC sub claim for the owner's identity")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        try:
            provision_initial_owner(db, args.owner_subject)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print("Owner provisioned. Protect this identity with MFA and retain provider recovery controls.")


if __name__ == "__main__":
    main()
