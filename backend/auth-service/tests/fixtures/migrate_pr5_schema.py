import os
import secrets

os.environ.setdefault("ENTITY_AUDIT_HMAC_KEY", secrets.token_urlsafe(48))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from entity_auth.bootstrap_owner import provision_initial_reviewer
from entity_auth.db import SessionLocal, User


command.upgrade(Config("alembic.ini"), "head")
with SessionLocal.begin() as db:
    provision_initial_reviewer(db, "legacy-owner", "legacy-reviewer")
engine = create_engine(os.environ["ENTITY_DATABASE_URL"])
inspector = inspect(engine)
expected_tables = {
    "entity_users", "entity_division_memberships", "entity_task_assignments",
    "entity_shared_resource_grants", "entity_token_sessions", "entity_action_approvals",
    "entity_resource_policies", "entity_admin_changes", "entity_audit_events",
    "alembic_version",
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
assert reviewer == "legacy-reviewer", "Legacy bootstrap did not establish an independent reviewer"
engine.dispose()
