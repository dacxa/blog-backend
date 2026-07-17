"""Add a version counter for user-session token revocation.

Revision ID: 20260717_02
Revises: 20260717_01
Create Date: 2026-07-17
"""
from alembic import context, op
from alembic.util import CommandError
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260717_02"
down_revision = "20260717_01"
branch_labels = None
depends_on = None


def _has_token_version_column() -> bool:
    return "token_version" in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")
    }


def _add_token_version_column() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _add_token_version_column()
        return

    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "users" in existing_tables and not _has_token_version_column():
        _add_token_version_column()


def downgrade() -> None:
    raise CommandError(
        "Session token version migration cannot be downgraded safely. "
        "Restore a database backup instead."
    )
