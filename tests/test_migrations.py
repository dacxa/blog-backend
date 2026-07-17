from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from io import StringIO
from pathlib import Path
import re
import subprocess
import sys

from alembic import command
from alembic.config import Config
from alembic.util import CommandError
import pytest
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from app.db.models import Base, User
from scripts.promote_admin import promote_user_to_admin


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATHS = (
    PROJECT_ROOT / "alembic" / "versions" / "20260717_01_content_moderation.py",
    PROJECT_ROOT / "alembic" / "versions" / "20260717_02_token_version.py",
)
REQUIREMENTS_LOCK_PATH = PROJECT_ROOT / "requirements.lock"


def migration_config(database_url: str | None = None, output_buffer=None) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output_buffer)
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def create_legacy_schema(
    database_url: str,
    *,
    reviewed_by_id_without_foreign_key: bool = False,
) -> None:
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String(50), nullable=False, unique=True),
        Column("email", String(255), nullable=False, unique=True),
        Column("password_hash", String(255), nullable=False),
        Column("is_active", Integer, nullable=False, server_default="1"),
        Column("created_at", DateTime, nullable=False),
    )
    categories = Table(
        "categories",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False, unique=True),
        Column("created_at", DateTime, nullable=False),
    )
    post_columns = [
        Column("id", Integer, primary_key=True),
        Column("author_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("category_id", Integer, ForeignKey("categories.id"), nullable=True),
        Column("title", String(200), nullable=False),
        Column("content", Text, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    ]
    if reviewed_by_id_without_foreign_key:
        post_columns.insert(3, Column("reviewed_by_id", Integer, nullable=True))
    posts = Table("posts", metadata, *post_columns)

    engine = create_engine(database_url)
    created_at = datetime(2026, 1, 1)
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(
                users.insert().values(
                    id=1,
                    username="legacy-user",
                    email="legacy@example.test",
                    password_hash="not-a-real-password",
                    is_active=1,
                    created_at=created_at,
                )
            )
            connection.execute(
                categories.insert().values(
                    id=1,
                    name="Legacy category",
                    created_at=created_at,
                )
            )
            connection.execute(
                posts.insert().values(
                    id=1,
                    author_id=1,
                    category_id=1,
                    title="Legacy post",
                    content="Existing content must survive.",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
    finally:
        engine.dispose()


def test_upgrade_preserves_legacy_rows_and_adds_content_moderation_schema(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.sqlite'}"
    create_legacy_schema(database_url)

    config = migration_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        post_columns = {column["name"] for column in inspector.get_columns("posts")}
        post_indexes = {index["name"] for index in inspector.get_indexes("posts")}

        assert {"role", "token_version"} <= user_columns
        assert {
            "status",
            "reviewed_by_id",
            "reviewed_at",
            "review_note",
            "published_at",
        } <= post_columns
        assert "ix_posts_status_published_at" in post_indexes
        assert "ix_posts_reviewed_by_id" in post_indexes
        assert "ix_posts_author_id" not in post_indexes
        assert "ix_posts_category_id" not in post_indexes
        assert any(
            foreign_key["constrained_columns"] == ["reviewed_by_id"]
            and foreign_key["referred_table"] == "users"
            for foreign_key in inspector.get_foreign_keys("posts")
        )

        metadata = MetaData()
        users = Table("users", metadata, autoload_with=engine)
        posts = Table("posts", metadata, autoload_with=engine)
        with engine.connect() as connection:
            assert connection.execute(select(users.c.role).where(users.c.id == 1)).scalar_one() == "user"
            assert (
                connection.execute(select(users.c.token_version).where(users.c.id == 1)).scalar_one()
                == 0
            )
            legacy_post = connection.execute(
                select(posts.c.title, posts.c.content, posts.c.status).where(posts.c.id == 1)
            ).one()
            assert legacy_post == ("Legacy post", "Existing content must survive.", "pending")
    finally:
        engine.dispose()


def test_promote_admin_help_requires_no_database_credentials() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/promote_admin.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--username" in result.stdout
    assert "--email" in result.stdout


def test_downgrade_rejects_bootstrap_revision_without_mutating_legacy_schema(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.sqlite'}"
    create_legacy_schema(database_url)
    config = migration_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        before_user_columns = {column["name"] for column in inspector.get_columns("users")}
        before_post_columns = {column["name"] for column in inspector.get_columns("posts")}

        with pytest.raises(CommandError, match="backup"):
            command.downgrade(config, "base")

        inspector = inspect(engine)
        assert before_user_columns == {column["name"] for column in inspector.get_columns("users")}
        assert before_post_columns == {column["name"] for column in inspector.get_columns("posts")}
    finally:
        engine.dispose()


def test_upgrade_adds_missing_reviewer_foreign_key_to_legacy_reviewer_column(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy-reviewer.sqlite'}"
    create_legacy_schema(database_url, reviewed_by_id_without_foreign_key=True)

    command.upgrade(migration_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        foreign_keys = inspect(engine).get_foreign_keys("posts")
        assert any(
            foreign_key["name"] == "fk_posts_reviewed_by_id_users"
            and foreign_key["constrained_columns"] == ["reviewed_by_id"]
            and foreign_key["referred_table"] == "users"
            for foreign_key in foreign_keys
        )
    finally:
        engine.dispose()


def test_upgrade_uses_explicit_alembic_database_url(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'environment.sqlite'}"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", database_url)

    command.upgrade(migration_config(), "head")

    engine = create_engine(database_url)
    try:
        assert {"users", "categories", "posts", "likes", "email_verifications"} <= set(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()


def test_upgrade_rejects_placeholder_url_without_explicit_database_url(monkeypatch) -> None:
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="ALEMBIC_DATABASE_URL"):
        command.upgrade(migration_config(), "head")


def test_migration_is_not_coupled_to_runtime_orm_metadata() -> None:
    for migration_path in MIGRATION_PATHS:
        source = migration_path.read_text(encoding="utf-8")

        assert "app.db.models" not in source
        assert "Base.metadata" not in source
        assert "create_all" not in source


def test_upgrade_empty_sqlite_creates_complete_content_moderation_schema(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'empty.sqlite'}"

    command.upgrade(migration_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {"users", "email_verifications", "categories", "posts", "likes"} <= set(
            inspector.get_table_names()
        )
        assert {"role", "token_version", "status"} <= {
            *(column["name"] for column in inspector.get_columns("users")),
            *(column["name"] for column in inspector.get_columns("posts")),
        }
        assert {
            "ix_posts_author_id",
            "ix_posts_category_id",
            "ix_posts_reviewed_by_id",
            "ix_posts_status_published_at",
        } <= {index["name"] for index in inspector.get_indexes("posts")}
    finally:
        engine.dispose()


def test_mysql_offline_render_uses_native_content_moderation_enums(monkeypatch) -> None:
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)
    output = StringIO()
    config = migration_config(
        "mysql+pymysql://user:password@localhost/blog",
        output_buffer=output,
    )
    config.cmd_opts = Namespace(x=["assume_empty_schema=true"])

    command.upgrade(config, "head", sql=True)

    rendered = output.getvalue()
    assert "ENUM('user','admin')" in rendered
    assert "ENUM('pending','published','rejected')" in rendered
    assert "token_version INTEGER NOT NULL DEFAULT 0" in rendered


def test_mysql_offline_render_requires_explicit_empty_schema_assumption(monkeypatch) -> None:
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)
    config = migration_config("mysql+pymysql://user:password@localhost/blog")

    with pytest.raises(CommandError, match="assume_empty_schema=true"):
        command.upgrade(config, "head", sql=True)


def test_mysql_database_url_builder_encodes_special_credentials() -> None:
    from app.db.url import build_mysql_database_url

    url = build_mysql_database_url(
        username="user@:/name",
        password="password@:/value",
        host="db.example.test",
        port=3307,
        database="blog",
    )
    rendered = url.render_as_string(hide_password=False)

    assert "user%40%3A%2Fname" in rendered
    assert "password%40%3A%2Fvalue" in rendered
    parsed = make_url(rendered)
    assert parsed.username == "user@:/name"
    assert parsed.password == "password@:/value"
    assert parsed.host == "db.example.test"
    assert parsed.port == 3307
    assert parsed.database == "blog"


def test_mysql_database_url_builder_is_not_coupled_to_settings_or_dotenv() -> None:
    source = (PROJECT_ROOT / "app" / "db" / "url.py").read_text(encoding="utf-8")

    assert "app.core.config" not in source
    assert "Settings" not in source
    assert ".env" not in source


def test_requirements_lock_contains_exact_direct_runtime_and_test_dependencies() -> None:
    locked_lines = [
        line.strip()
        for line in REQUIREMENTS_LOCK_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ] == [
        "fastapi",
        "uvicorn[standard]",
        "pydantic-settings",
        "SQLAlchemy",
        "pymysql",
        "PyJWT",
        "passlib[bcrypt]",
        "email-validator",
        "python-multipart",
    ]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,-]+\])?==[^=\s]+", line) for line in locked_lines)
    dependency_names = {
        line.split("==", 1)[0].split("[", 1)[0].lower().replace("_", "-")
        for line in locked_lines
    }
    assert {
        "fastapi",
        "alembic",
        "uvicorn",
        "pydantic-settings",
        "sqlalchemy",
        "pymysql",
        "pyjwt",
        "passlib",
        "email-validator",
        "python-multipart",
        "pytest",
        "httpx",
        "starlette",
        "anyio",
        "pydantic-core",
        "pluggy",
        "typing-extensions",
    } <= dependency_names


def test_promote_user_to_admin_updates_an_existing_sqlite_user() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        with session_factory() as session:
            user = User(
                username="member",
                email="member@example.test",
                password_hash="not-a-real-password",
                role="user",
            )
            session.add(user)
            session.commit()

            promoted_user_id = promote_user_to_admin(session, username="member")

            assert promoted_user_id == user.id
            assert session.get(User, user.id).role == "admin"
            assert promote_user_to_admin(session, username="absent") is None
    finally:
        engine.dispose()
