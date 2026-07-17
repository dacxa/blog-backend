"""Add durable roles and post content-moderation fields.

Revision ID: 20260717_01
Revises:
Create Date: 2026-07-17

MySQL DDL may implicitly commit, so a database server cannot guarantee a
transactional rollback if a migration is interrupted.
"""
from typing import Iterable

from alembic import context, op
from alembic.util import CommandError
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.sql.type_api import TypeEngine


# revision identifiers, used by Alembic.
revision = "20260717_01"
down_revision = None
branch_labels = None
depends_on = None


def _dialect_name() -> str:
    return context.get_context().dialect.name


def _enum_type(name: str, values: tuple[str, ...]) -> TypeEngine:
    """Use real ENUM values on MySQL and CHECK-backed values elsewhere."""
    if _dialect_name() == "mysql":
        return mysql.ENUM(*values)
    return sa.Enum(*values, name=name, native_enum=True, create_constraint=True)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _ensure_index(table_name: str, index_name: str, columns: Iterable[str]) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, list(columns))


def _batch_recreate_mode() -> str:
    # SQLite cannot add foreign keys after table creation. Recreate keeps the
    # legacy rows while allowing the reviewer foreign key and enum CHECKs.
    return "always" if _dialect_name() == "sqlite" else "auto"


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            _enum_type("user_role", ("user", "admin")),
            nullable=False,
            server_default=sa.text("'user'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])


def _create_email_verifications_table() -> None:
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("expire_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_email_verifications_email", "email_verifications", ["email"])
    op.create_index("ix_email_verifications_code", "email_verifications", ["code"])


def _create_categories_table() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )


def _create_posts_table() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            _enum_type("post_status", ("pending", "published", "rejected")),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name="fk_posts_reviewed_by_id_users",
        ),
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_category_id", "posts", ["category_id"])
    op.create_index("ix_posts_reviewed_by_id", "posts", ["reviewed_by_id"])
    op.create_index("ix_posts_status_published_at", "posts", ["status", "published_at"])


def _create_likes_table() -> None:
    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.UniqueConstraint("user_id", "post_id", name="uq_like_user_post"),
    )
    op.create_index("ix_likes_user_id", "likes", ["user_id"])
    op.create_index("ix_likes_post_id", "likes", ["post_id"])


def _create_missing_base_tables(existing_tables: set[str]) -> None:
    if "users" not in existing_tables:
        _create_users_table()
    if "email_verifications" not in existing_tables:
        _create_email_verifications_table()
    if "categories" not in existing_tables:
        _create_categories_table()
    if "posts" not in existing_tables:
        _create_posts_table()
    if "likes" not in existing_tables:
        _create_likes_table()


def _add_user_role() -> None:
    if "role" in _columns("users"):
        return

    with op.batch_alter_table("users", recreate=_batch_recreate_mode()) as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                _enum_type("user_role", ("user", "admin")),
                nullable=False,
                server_default=sa.text("'user'"),
            )
        )


def _add_post_moderation_columns() -> None:
    existing_columns = _columns("posts")
    if {
        "status",
        "reviewed_by_id",
        "reviewed_at",
        "review_note",
        "published_at",
    }.issubset(existing_columns):
        return

    with op.batch_alter_table("posts", recreate=_batch_recreate_mode()) as batch_op:
        if "status" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "status",
                    _enum_type("post_status", ("pending", "published", "rejected")),
                    nullable=False,
                    server_default=sa.text("'pending'"),
                )
            )
        if "reviewed_by_id" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "reviewed_by_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id", name="fk_posts_reviewed_by_id_users"),
                    nullable=True,
                )
            )
        if "reviewed_at" not in existing_columns:
            batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        if "review_note" not in existing_columns:
            batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        if "published_at" not in existing_columns:
            batch_op.add_column(sa.Column("published_at", sa.DateTime(), nullable=True))


def _ensure_post_indexes() -> None:
    _ensure_index("posts", "ix_posts_reviewed_by_id", ("reviewed_by_id",))
    _ensure_index("posts", "ix_posts_status_published_at", ("status", "published_at"))


def _has_reviewer_foreign_key() -> bool:
    return any(
        foreign_key["name"] == "fk_posts_reviewed_by_id_users"
        and foreign_key["constrained_columns"] == ["reviewed_by_id"]
        and foreign_key["referred_table"] == "users"
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("posts")
    )


def _ensure_reviewer_foreign_key() -> None:
    if _has_reviewer_foreign_key():
        return

    with op.batch_alter_table("posts", recreate=_batch_recreate_mode()) as batch_op:
        batch_op.create_foreign_key(
            "fk_posts_reviewed_by_id_users",
            "users",
            ["reviewed_by_id"],
            ["id"],
        )


def _assume_empty_schema_for_offline_sql() -> bool:
    arguments = context.get_x_argument(as_dictionary=True)
    return arguments.get("assume_empty_schema", "").lower() == "true"


def upgrade() -> None:
    if context.is_offline_mode():
        if not _assume_empty_schema_for_offline_sql():
            raise CommandError(
                "Offline SQL cannot inspect an existing schema. Re-run with "
                "-x assume_empty_schema=true only when the target database is empty."
            )
        _create_missing_base_tables(set())
        return

    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    _create_missing_base_tables(existing_tables)

    if "users" in existing_tables:
        _add_user_role()
    if "posts" in existing_tables:
        _add_post_moderation_columns()
        _ensure_reviewer_foreign_key()
        _ensure_post_indexes()


def downgrade() -> None:
    raise CommandError(
        "This bootstrap migration cannot safely distinguish pre-existing tables from "
        "tables it created. Restore a database backup instead of downgrading it."
    )
