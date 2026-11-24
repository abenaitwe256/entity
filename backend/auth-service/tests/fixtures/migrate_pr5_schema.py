import os
import secrets
from datetime import timedelta

os.environ.setdefault("ENTITY_AUDIT_HMAC_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("ENTITY_ORIGINAL_OWNER_SUBJECT", "legacy-owner")
os.environ.setdefault("ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT", "legacy-reviewer")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from entity_auth import bootstrap_owner
from entity_auth.db import (
    ORIGINAL_OWNER_KEY, OriginalOwnerIdentity, SessionLocal, User, utcnow,
)
from entity_auth.oidc import VerifiedToken


command.upgrade(Config("alembic.ini"), "head")

def _verified(sub: str, jti: str) -> VerifiedToken:
    now = utcnow()
    return VerifiedToken(
        claims={
            "sub": sub,
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iat": int(now.timestamp()),
            "jti": jti,
            "amr": ["mfa"],
            "auth_time": now.timestamp(),
        },
        token_hash=(jti * 64)[:64],
    )


bootstrap_owner.verify_bearer = lambda token: {
    "owner-bootstrap-token": _verified("legacy-owner", "owner"),
    "reviewer-bootstrap-token": _verified("legacy-reviewer", "reviewer"),
}[token]
with SessionLocal.begin() as db:
    bootstrap_owner.bootstrap_original_owner(
        db, "owner-bootstrap-token", "reviewer-bootstrap-token",
    )
engine = create_engine(os.environ["ENTITY_DATABASE_URL"])
inspector = inspect(engine)
expected_tables = {
    "entity_users", "entity_division_memberships", "entity_task_assignments",
    "entity_shared_resource_grants", "entity_token_sessions", "entity_action_approvals",
    "entity_resource_policies", "entity_admin_changes", "entity_audit_events",
    "entity_original_owner_identity", "alembic_version",
}
missing = expected_tables - set(inspector.get_table_names())
assert not missing, f"Migration omitted expected tables: {sorted(missing)}"
approval_columns = {column["name"] for column in inspector.get_columns("entity_action_approvals")}
assert {
    "resource_owner_subject", "resource_version", "required_approver_rank", "consumed_at",
} <= approval_columns
with engine.connect() as connection:
    subject = connection.scalar(text(
        "SELECT subject FROM entity_users WHERE subject = 'legacy-owner'"
    ))
assert subject == "legacy-owner", "Migration did not preserve the existing owner account"
with engine.connect() as connection:
    reviewer = connection.scalar(text(
        "SELECT subject FROM entity_users WHERE subject = 'legacy-reviewer' AND rank = 1"
    ))
    identity = connection.execute(text(
        "SELECT identity_id, owner_user_id, oidc_issuer, oidc_subject "
        "FROM entity_original_owner_identity WHERE identity_key = :identity_key"
    ), {"identity_key": ORIGINAL_OWNER_KEY}).one_or_none()
    trigger_names = set(connection.scalars(text(
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
        "AND tgname IN ('entity_original_owner_identity_insert_guard', 'entity_original_owner_anchor_immutable', "
        "'entity_original_owner_account_immutable')"
    )).all())
assert reviewer == "legacy-reviewer", "Legacy bootstrap did not establish an independent reviewer"
assert identity and identity.oidc_subject == "legacy-owner"
assert trigger_names == {
    "entity_original_owner_identity_insert_guard",
    "entity_original_owner_anchor_immutable",
    "entity_original_owner_account_immutable",
}, "Migration did not install immutable Owner protections"
engine.dispose()
