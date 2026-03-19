"""income_settlement_ledger

Revision ID: b3f9a7c2d1e4
Revises: 7f7d6e241bcd
Create Date: 2026-03-19 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f9a7c2d1e4"
down_revision = "7f7d6e241bcd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("gross_amount", sa.Float(), nullable=False),
        sa.Column("net_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("payment_ref", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_payouts_actor_period", "payouts", ["actor_type", "actor_id", "period_start", "period_end"])
    op.create_index("idx_payouts_status_created", "payouts", ["status", "created_at"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("entry_code", sa.String(length=64), nullable=False),
        sa.Column("reference_key", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("payout_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["payout_id"], ["payouts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_key"),
    )
    op.create_index("idx_ledger_actor_effective", "ledger_entries", ["actor_type", "actor_id", "effective_at"])
    op.create_index("idx_ledger_status_effective", "ledger_entries", ["status", "effective_at"])
    op.create_index("idx_ledger_source", "ledger_entries", ["source_type", "source_id"])
    op.create_index("idx_ledger_payout", "ledger_entries", ["payout_id"])


def downgrade():
    op.drop_index("idx_ledger_payout", table_name="ledger_entries")
    op.drop_index("idx_ledger_source", table_name="ledger_entries")
    op.drop_index("idx_ledger_status_effective", table_name="ledger_entries")
    op.drop_index("idx_ledger_actor_effective", table_name="ledger_entries")
    op.drop_table("ledger_entries")

    op.drop_index("idx_payouts_status_created", table_name="payouts")
    op.drop_index("idx_payouts_actor_period", table_name="payouts")
    op.drop_table("payouts")
