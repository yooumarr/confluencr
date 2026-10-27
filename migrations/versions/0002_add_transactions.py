"""Store balances in cents and add immutable ledger transactions.

Revision ID: 0002_add_transactions
Revises: 0001_create_accounts
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_transactions"
down_revision = "0001_create_accounts"
branch_labels = None
depends_on = None

MAX_BALANCE_CENTS = 9_000_000_000_000_000_000


def upgrade() -> None:
    op.execute("UPDATE accounts SET balance = CAST(ROUND(balance * 100) AS INTEGER)")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("ck_accounts_balance_nonnegative", type_="check")
        batch_op.alter_column(
            "balance",
            new_column_name="balance_cents",
            existing_type=sa.Numeric(precision=18, scale=2),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )
        batch_op.create_check_constraint(
            "ck_accounts_balance_cents_range",
            f"balance_cents >= 0 AND balance_cents <= {MAX_BALANCE_CENTS}",
        )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=6), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference_id", sa.String(length=200), nullable=False),
        sa.Column("transfer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("type IN ('credit', 'debit')", name="ck_transactions_type"),
        sa.CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "reference_id", name="uq_transactions_account_reference"
        ),
    )
    op.create_index(
        "ix_transactions_account_created",
        "transactions",
        ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_account_created", table_name="transactions")
    op.drop_table("transactions")
    op.execute("UPDATE accounts SET balance_cents = CAST(balance_cents AS NUMERIC) / 100")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("ck_accounts_balance_cents_range", type_="check")
        batch_op.alter_column(
            "balance_cents",
            new_column_name="balance",
            existing_type=sa.Integer(),
            type_=sa.Numeric(precision=18, scale=2),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )
        batch_op.create_check_constraint(
            "ck_accounts_balance_nonnegative",
            "balance >= 0",
        )
