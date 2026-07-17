from datetime import datetime, timedelta
import json
from pathlib import Path
import re

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, EmailVerification
from app.services import email_service
from app.services import verification_service


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_frontend_api_client_uses_api_subdomain_and_cross_site_credentials() -> None:
    api_client = (PROJECT_ROOT / "public" / "js" / "api.js").read_text(
        encoding="utf-8"
    )

    request_options = re.search(
        r"var requestOptions\s*=\s*\{(.*?)\};", api_client, re.DOTALL
    )

    assert 'var API_BASE = "https://api.solocraft.xyz";' in api_client
    assert request_options is not None
    assert 'credentials: "include"' in request_options.group(1)
    assert "global.fetch(API_BASE + path, requestOptions)" in api_client


def test_registration_requests_use_api_subdomain_and_cross_site_credentials() -> None:
    for registration_path in (
        PROJECT_ROOT / "register.html",
        PROJECT_ROOT / "public" / "register.html",
    ):
        registration_page = registration_path.read_text(encoding="utf-8")

        assert 'const API_BASE = "https://api.solocraft.xyz";' in registration_page
        for endpoint in ("request-code", "verify-code"):
            request = re.search(
                rf"fetch\(`\$\{{API_BASE\}}/auth/register/{endpoint}`,\s*\{{(.*?)\}}\s*\);",
                registration_page,
                re.DOTALL,
            )
            assert request is not None
            assert 'credentials: "include"' in request.group(1)


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


def test_vercel_does_not_proxy_api_requests_to_the_ecs_backend() -> None:
    assert not (PROJECT_ROOT / "vercel.json").exists()


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
