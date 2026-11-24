from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_original_owner_identity"
down_revision = "0001_authz_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_original_owner_identity",
        sa.Column("identity_key", sa.String(32), nullable=False),
        sa.Column("identity_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("oidc_issuer", sa.String(512), nullable=False),
        sa.Column("oidc_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "identity_key = 'original-founder'",
            name="ck_original_owner_identity_singleton",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["entity_users.id"],
            name="fk_original_owner_user", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("identity_key"),
        sa.UniqueConstraint("identity_id", name="uq_original_owner_identity_id"),
        sa.UniqueConstraint("owner_user_id", name="uq_original_owner_user"),
        sa.UniqueConstraint(
            "oidc_issuer", "oidc_subject", name="uq_original_owner_oidc_identity",
        ),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION entity_validate_original_owner_identity()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            owner_rank integer;
            owner_subject text;
        BEGIN
            SELECT rank, subject INTO owner_rank, owner_subject
            FROM entity_users WHERE id = NEW.owner_user_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Original Owner account does not exist'
                    USING ERRCODE = '42501';
            END IF;
            IF owner_rank <> 0 OR owner_subject <> NEW.oidc_subject THEN
                RAISE EXCEPTION 'Owner anchor must match a Rank 0 account and its OIDC subject'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_original_owner_identity_insert_guard
        BEFORE INSERT ON entity_original_owner_identity
        FOR EACH ROW EXECUTE FUNCTION entity_validate_original_owner_identity()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION entity_reject_original_owner_anchor_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Original Owner identity binding is immutable'
                USING ERRCODE = '42501';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_original_owner_anchor_immutable
        BEFORE UPDATE OR DELETE ON entity_original_owner_identity
        FOR EACH ROW EXECUTE FUNCTION entity_reject_original_owner_anchor_change()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION entity_protect_original_owner_account()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM entity_original_owner_identity
                WHERE owner_user_id = OLD.id
            ) THEN
                RAISE EXCEPTION 'Original Owner account cannot be modified or deleted'
                    USING ERRCODE = '42501';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_original_owner_account_immutable
        BEFORE UPDATE OR DELETE ON entity_users
        FOR EACH ROW EXECUTE FUNCTION entity_protect_original_owner_account()
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Original Owner identity protection is forward-only. Use a reviewed recovery "
        "procedure and restore a verified backup rather than removing the Owner anchor."
    )
