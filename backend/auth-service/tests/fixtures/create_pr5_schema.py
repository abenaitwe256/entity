import os

from sqlalchemy import create_engine, text


engine = create_engine(os.environ["ENTITY_DATABASE_URL"])
statements = [
    """CREATE TABLE entity_users (
        id VARCHAR(36) PRIMARY KEY,
        subject VARCHAR(255) NOT NULL,
        rank INTEGER NOT NULL,
        active BOOLEAN NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        created_by VARCHAR(255),
        CONSTRAINT uq_entity_users_subject UNIQUE (subject),
        CONSTRAINT ck_entity_user_rank CHECK (rank BETWEEN 0 AND 6)
    )""",
    "CREATE INDEX ix_entity_users_subject ON entity_users (subject)",
    "CREATE UNIQUE INDEX uq_entity_single_owner ON entity_users (rank) WHERE rank = 0",
    """CREATE TABLE entity_division_memberships (
        id VARCHAR(36) PRIMARY KEY,
        subject VARCHAR(255) NOT NULL REFERENCES entity_users(subject) ON DELETE CASCADE,
        division VARCHAR(40) NOT NULL,
        assigned_by VARCHAR(255),
        created_at TIMESTAMPTZ NOT NULL,
        CONSTRAINT uq_subject_division UNIQUE (subject, division)
    )""",
    "CREATE INDEX ix_entity_division_memberships_subject ON entity_division_memberships (subject)",
    "CREATE INDEX ix_entity_division_memberships_division ON entity_division_memberships (division)",
    """CREATE TABLE entity_task_assignments (
        id VARCHAR(36) PRIMARY KEY,
        subject VARCHAR(255) NOT NULL REFERENCES entity_users(subject) ON DELETE CASCADE,
        division VARCHAR(40) NOT NULL,
        description TEXT NOT NULL,
        permissions JSON NOT NULL,
        resource_type VARCHAR(80),
        resource_id VARCHAR(255),
        starts_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ,
        assigned_by VARCHAR(255) NOT NULL
    )""",
    "CREATE INDEX ix_entity_task_assignments_subject ON entity_task_assignments (subject)",
    "CREATE INDEX ix_entity_task_assignments_division ON entity_task_assignments (division)",
    """CREATE TABLE entity_shared_resource_grants (
        id VARCHAR(36) PRIMARY KEY,
        subject VARCHAR(255) NOT NULL REFERENCES entity_users(subject) ON DELETE CASCADE,
        resource_type VARCHAR(80) NOT NULL,
        resource_id VARCHAR(255) NOT NULL,
        permission VARCHAR(24) NOT NULL,
        granted_by VARCHAR(255) NOT NULL,
        expires_at TIMESTAMPTZ,
        revoked_at TIMESTAMPTZ,
        CONSTRAINT uq_resource_grant UNIQUE (subject, resource_type, resource_id, permission)
    )""",
    "CREATE INDEX ix_entity_shared_resource_grants_subject ON entity_shared_resource_grants (subject)",
    """CREATE TABLE entity_token_sessions (
        id VARCHAR(36) PRIMARY KEY,
        subject VARCHAR(255) NOT NULL REFERENCES entity_users(subject) ON DELETE CASCADE,
        token_hash VARCHAR(64) NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        last_seen_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ
    )""",
    "CREATE INDEX ix_entity_token_sessions_subject ON entity_token_sessions (subject)",
    "CREATE INDEX ix_entity_token_sessions_expires_at ON entity_token_sessions (expires_at)",
    """CREATE TABLE entity_action_approvals (
        id VARCHAR(36) PRIMARY KEY,
        requester VARCHAR(255) NOT NULL REFERENCES entity_users(subject),
        approver VARCHAR(255),
        division VARCHAR(40) NOT NULL,
        action VARCHAR(24) NOT NULL,
        resource_type VARCHAR(80) NOT NULL,
        resource_id VARCHAR(255) NOT NULL,
        classification VARCHAR(24) NOT NULL,
        risk VARCHAR(16) NOT NULL,
        environment VARCHAR(16) NOT NULL,
        task_id VARCHAR(36) NOT NULL,
        status VARCHAR(16) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        decided_at TIMESTAMPTZ
    )""",
    "CREATE INDEX ix_entity_action_approvals_requester ON entity_action_approvals (requester)",
    "CREATE INDEX ix_entity_action_approvals_approver ON entity_action_approvals (approver)",
    """CREATE TABLE entity_audit_events (
        id VARCHAR(36) PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL,
        actor VARCHAR(255) NOT NULL,
        event_type VARCHAR(80) NOT NULL,
        outcome VARCHAR(16) NOT NULL,
        detail JSON NOT NULL,
        previous_hash VARCHAR(64) NOT NULL,
        event_hash VARCHAR(64) NOT NULL UNIQUE
    )""",
    "CREATE INDEX ix_entity_audit_events_created_at ON entity_audit_events (created_at)",
    """INSERT INTO entity_users (id, subject, rank, active, created_at, created_by)
       VALUES ('00000000-0000-4000-8000-000000000001', 'legacy-owner', 0, TRUE, NOW(), 'bootstrap')""",
]
with engine.begin() as connection:
    for statement in statements:
        connection.execute(text(statement))
engine.dispose()
