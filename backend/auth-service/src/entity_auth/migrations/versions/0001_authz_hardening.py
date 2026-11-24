from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_authz_hardening"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _checks(table: str) -> set[str]:
    return {item.get("name") for item in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _create_missing_tables() -> None:
    tables = _tables()
    if "entity_users" not in tables:
        op.create_table(
            "entity_users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.UniqueConstraint("subject", name="uq_entity_users_subject"),
            sa.CheckConstraint("rank BETWEEN 0 AND 6", name="ck_entity_user_rank"),
        )
    tables = _tables()
    if "entity_division_memberships" not in tables:
        op.create_table(
            "entity_division_memberships",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subject", sa.String(255), sa.ForeignKey("entity_users.subject", ondelete="CASCADE"), nullable=False),
            sa.Column("division", sa.String(40), nullable=False),
            sa.Column("assigned_by", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("subject", "division", name="uq_subject_division"),
        )
    tables = _tables()
    if "entity_task_assignments" not in tables:
        op.create_table(
            "entity_task_assignments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subject", sa.String(255), sa.ForeignKey("entity_users.subject", ondelete="CASCADE"), nullable=False),
            sa.Column("division", sa.String(40), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=True),
            sa.Column("resource_id", sa.String(255), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_by", sa.String(255), nullable=False),
        )
    tables = _tables()
    if "entity_shared_resource_grants" not in tables:
        op.create_table(
            "entity_shared_resource_grants",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subject", sa.String(255), sa.ForeignKey("entity_users.subject", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=False),
            sa.Column("resource_id", sa.String(255), nullable=False),
            sa.Column("permission", sa.String(24), nullable=False),
            sa.Column("granted_by", sa.String(255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("subject", "resource_type", "resource_id", "permission", name="uq_resource_grant"),
        )
    tables = _tables()
    if "entity_resource_policies" not in tables:
        op.create_table(
            "entity_resource_policies",
            sa.Column("resource_type", sa.String(80), primary_key=True),
            sa.Column("resource_id", sa.String(255), primary_key=True),
            sa.Column("owner_subject", sa.String(255), sa.ForeignKey("entity_users.subject", ondelete="RESTRICT"), nullable=False),
            sa.Column("division", sa.String(40), nullable=False),
            sa.Column("classification", sa.String(24), nullable=False),
            sa.Column("risk", sa.String(16), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.String(255), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("classification IN ('public', 'internal', 'restricted', 'highly_restricted')", name="ck_resource_policy_classification"),
            sa.CheckConstraint("risk IN ('low', 'moderate', 'high', 'critical')", name="ck_resource_policy_risk"),
            sa.CheckConstraint("version >= 1", name="ck_resource_policy_version"),
        )
    tables = _tables()
    if "entity_token_sessions" not in tables:
        op.create_table(
            "entity_token_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subject", sa.String(255), sa.ForeignKey("entity_users.subject", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )
    tables = _tables()
    if "entity_action_approvals" not in tables:
        op.create_table(
            "entity_action_approvals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("requester", sa.String(255), sa.ForeignKey("entity_users.subject"), nullable=False),
            sa.Column("approver", sa.String(255), nullable=True),
            sa.Column("division", sa.String(40), nullable=False),
            sa.Column("action", sa.String(24), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=False),
            sa.Column("resource_id", sa.String(255), nullable=False),
            sa.Column("classification", sa.String(24), nullable=False),
            sa.Column("risk", sa.String(16), nullable=False),
            sa.Column("environment", sa.String(16), nullable=False),
            sa.Column("task_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resource_owner_subject", sa.String(255), nullable=True),
            sa.Column("resource_version", sa.Integer(), nullable=True),
            sa.Column("required_approver_rank", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_action_approval_status"),
            sa.CheckConstraint("required_approver_rank IN (0, 1)", name="ck_action_approval_reviewer_rank"),
        )
    tables = _tables()
    if "entity_admin_changes" not in tables:
        op.create_table(
            "entity_admin_changes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("requester", sa.String(255), sa.ForeignKey("entity_users.subject"), nullable=False),
            sa.Column("operation_type", sa.String(32), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("required_approver_rank", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("approver", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_admin_change_status"),
            sa.CheckConstraint("required_approver_rank = 1", name="ck_admin_change_reviewer_rank"),
        )
    tables = _tables()
    if "entity_audit_events" not in tables:
        op.create_table(
            "entity_audit_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("outcome", sa.String(16), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=False),
            sa.Column("previous_hash", sa.String(64), nullable=False),
            sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        )

    index_specs = {
        "entity_users": (("ix_entity_users_subject", ["subject"], False), ("uq_entity_single_owner", ["rank"], True)),
        "entity_division_memberships": (("ix_entity_division_memberships_subject", ["subject"], False), ("ix_entity_division_memberships_division", ["division"], False)),
        "entity_task_assignments": (("ix_entity_task_assignments_subject", ["subject"], False), ("ix_entity_task_assignments_division", ["division"], False)),
        "entity_shared_resource_grants": (("ix_entity_shared_resource_grants_subject", ["subject"], False),),
        "entity_resource_policies": (("ix_entity_resource_policies_owner_subject", ["owner_subject"], False), ("ix_entity_resource_policies_division", ["division"], False)),
        "entity_token_sessions": (("ix_entity_token_sessions_subject", ["subject"], False), ("ix_entity_token_sessions_expires_at", ["expires_at"], False)),
        "entity_action_approvals": (("ix_entity_action_approvals_requester", ["requester"], False), ("ix_entity_action_approvals_approver", ["approver"], False)),
        "entity_admin_changes": (("ix_entity_admin_changes_requester", ["requester"], False), ("ix_entity_admin_changes_approver", ["approver"], False)),
        "entity_audit_events": (("ix_entity_audit_events_created_at", ["created_at"], False),),
    }
    for table, specs in index_specs.items():
        for name, columns, unique in specs:
            if name not in _indexes(table):
                kwargs = {"postgresql_where": sa.text("rank = 0")} if name == "uq_entity_single_owner" else {}
                op.create_index(name, table, columns, unique=unique, **kwargs)


def _upgrade_action_approval_columns() -> None:
    table = "entity_action_approvals"
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    additions = (
        ("resource_owner_subject", sa.String(255), True, None),
        ("resource_version", sa.Integer(), True, None),
        ("required_approver_rank", sa.Integer(), False, "0"),
        ("consumed_at", sa.DateTime(timezone=True), True, None),
    )
    for name, type_, nullable, default in additions:
        if name not in columns:
            kwargs = {"nullable": nullable}
            if default is not None:
                kwargs["server_default"] = default
            op.add_column(table, sa.Column(name, type_, **kwargs))
    checks = _checks(table)
    if "ck_action_approval_status" not in checks:
        op.create_check_constraint(
            "ck_action_approval_status", table,
            "status IN ('pending', 'approved', 'rejected')",
        )
    if "ck_action_approval_reviewer_rank" not in checks:
        op.create_check_constraint(
            "ck_action_approval_reviewer_rank", table,
            "required_approver_rank IN (0, 1)",
        )


def upgrade() -> None:
    _create_missing_tables()
    _upgrade_action_approval_columns()


def downgrade() -> None:
    raise RuntimeError(
        "This security migration is forward-only. Restore a verified database backup "
        "instead of dropping authorization and audit data."
    )
