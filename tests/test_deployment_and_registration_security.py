from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, EmailVerification
from app.services import email_service
from app.services import verification_service


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def verification_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield session_factory

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_request_code_rejects_a_recent_unconsumed_code(
    monkeypatch, verification_session_factory
) -> None:
    sent_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(verification_service, "SessionLocal", verification_session_factory)
    monkeypatch.setattr(
        verification_service,
        "send_verification_code",
        lambda email, code: sent_messages.append((email, code)),
    )

    with verification_session_factory() as session:
        session.add(
            EmailVerification(
                email="new-user@example.com",
                code="123456",
                expire_at=datetime.utcnow() + timedelta(minutes=5),
            )
        )
        session.commit()

    with pytest.raises(HTTPException) as raised:
        verification_service.request_code("new-user@example.com")

    assert raised.value.status_code == 429
    assert sent_messages == []


def test_verification_codes_use_a_cryptographic_random_source(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        email_service.secrets,
        "randbelow",
        lambda upper_bound: calls.append(upper_bound) or 42,
    )

    assert email_service.generate_code() == "000042"
    assert calls == [1_000_000]


def test_vercel_proxies_api_requests_to_the_ecs_backend() -> None:
    configuration = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert "redirects" not in configuration
    assert {
        "source": "/api/:path*",
        "destination": "https://api.solocraft.xyz/:path*",
    } in configuration["rewrites"]
    assert "functions" not in configuration


def test_vercel_build_excludes_the_python_backend() -> None:
    ignored_paths = {
        line.strip()
        for line in (PROJECT_ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {
        "main.py",
        "app/",
        "alembic/",
        "alembic.ini",
        "requirements.txt",
        "requirements.lock",
        "**/*.py",
    } <= ignored_paths
