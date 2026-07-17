from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.models import Base, User
from app.db.session import get_db
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.posts import router as posts_router
from main import app as main_app


@pytest.fixture()
def client_and_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(posts_router)
    app.include_router(admin_router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, base_url="https://testserver") as client:
        yield client, testing_session_local

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_user(session_factory, *, username: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash="unused-in-this-test",
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def create_login_user(session_factory, *, username: str, password: str) -> User:
    with session_factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password(password),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def authorization_header(user_id: int, *, version: int = 0) -> dict[str, str]:
    token = create_access_token(
        data={"sub": str(user_id), "ver": version},
        expires_delta=timedelta(minutes=5),
    )
    return {"Authorization": f"Bearer {token}"}


def test_database_rejects_unknown_user_role(client_and_session) -> None:
    _, session_factory = client_and_session

    with session_factory() as session:
        session.add(
            User(
                username="unexpected-role",
                email="unexpected-role@example.com",
                password_hash="unused-in-this-test",
                role="unexpected",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_auth_me_returns_database_admin_role(client_and_session) -> None:
    client, session_factory = client_and_session
    admin = create_user(session_factory, username="admin", role="admin")

    response = client.get("/auth/me", headers=authorization_header(admin.id))

    assert response.status_code == 200
    assert response.json() == {
        "id": admin.id,
        "username": "admin",
        "role": "admin",
        "is_active": True,
    }


def test_https_login_starts_cookie_session_and_logout_revokes_it(client_and_session) -> None:
    client, session_factory = client_and_session
    password = "cookie-session-password"
    user = create_login_user(
        session_factory,
        username="cookie-user",
        password=password,
    )

    login_response = client.post(
        "/auth/login",
        json={"username": user.username, "password": password},
    )

    assert login_response.status_code == 200
    cookie = login_response.headers["set-cookie"].lower()
    assert "access_token=" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert settings.JWT_ACCESS_EXPIRE_SECONDS == 8 * 60 * 60
    assert f"max-age={8 * 60 * 60}" in cookie
    captured_cookie = client.cookies.get("access_token")
    assert captured_cookie

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["id"] == user.id

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 204
    assert client.get("/auth/me").status_code == 401

    replay_response = client.get(
        "/auth/me",
        cookies={"access_token": captured_cookie},
    )
    assert replay_response.status_code == 401


def test_logout_revokes_the_bearer_returned_by_login(client_and_session) -> None:
    client, session_factory = client_and_session
    password = "bearer-session-password"
    user = create_login_user(
        session_factory,
        username="bearer-session-user",
        password=password,
    )

    login_response = client.post(
        "/auth/login",
        json={"username": user.username, "password": password},
    )
    assert login_response.status_code == 200
    bearer = login_response.json()["access_token"]

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 204

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {bearer}"})
    assert response.status_code == 401


def test_auth_me_rejects_a_token_without_a_session_version(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="legacy-token-user", role="user")
    token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=5),
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_auth_me_rejects_a_token_with_a_non_integer_session_version(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="invalid-version-user", role="user")
    token = create_access_token(
        data={"sub": str(user.id), "ver": "0"},
        expires_delta=timedelta(minutes=5),
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_auth_me_rejects_a_token_with_a_stale_session_version(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="stale-version-user", role="user")

    response = client.get("/auth/me", headers=authorization_header(user.id, version=1))

    assert response.status_code == 401


def test_new_sqlite_users_reject_null_session_versions(client_and_session) -> None:
    _, session_factory = client_and_session

    with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO users "
                    "(username, email, password_hash, role, is_active, created_at, token_version) "
                    "VALUES "
                    "('null-version', 'null-version@example.com', 'unused-in-this-test', "
                    "'user', 1, CURRENT_TIMESTAMP, NULL)"
                )
            )
            session.commit()
        session.rollback()


def test_bearer_token_takes_priority_over_session_cookie(client_and_session) -> None:
    client, session_factory = client_and_session
    password = "cookie-user-password"
    cookie_user = create_login_user(
        session_factory,
        username="cookie-user",
        password=password,
    )
    bearer_user = create_user(session_factory, username="bearer-user", role="user")

    login_response = client.post(
        "/auth/login",
        json={"username": cookie_user.username, "password": password},
    )
    assert login_response.status_code == 200

    response = client.get("/auth/me", headers=authorization_header(bearer_user.id))
    assert response.status_code == 200
    assert response.json()["id"] == bearer_user.id


def test_cors_allows_only_configured_credentialed_origin() -> None:
    with TestClient(main_app, base_url="https://testserver") as client:
        allowed_response = client.options(
            "/auth/me",
            headers={
                "Origin": "https://solocraft.xyz",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        delete_response = client.options(
            "/auth/me",
            headers={
                "Origin": "https://solocraft.xyz",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        unneeded_header_response = client.options(
            "/auth/me",
            headers={
                "Origin": "https://solocraft.xyz",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Unneeded",
            },
        )
        denied_response = client.options(
            "/auth/me",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed_response.status_code == 200
    assert allowed_response.headers["access-control-allow-origin"] == "https://solocraft.xyz"
    assert allowed_response.headers["access-control-allow-credentials"] == "true"
    assert "authorization" in allowed_response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_response.headers["access-control-allow-headers"].lower()
    assert delete_response.status_code == 400
    assert unneeded_header_response.status_code == 400
    assert "DELETE" not in delete_response.headers.get("access-control-allow-methods", "")
    assert "x-unneeded" not in unneeded_header_response.headers.get(
        "access-control-allow-headers", ""
    ).lower()
    assert denied_response.status_code == 400
    assert "access-control-allow-origin" not in denied_response.headers


def test_regular_user_is_forbidden_from_admin_dependency(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="member", role="user")

    response = client.get("/admin/posts", headers=authorization_header(user.id))

    assert response.status_code == 403


def test_legacy_unverified_registration_endpoint_is_not_available(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/auth/register",
        json={
            "username": "unverified",
            "email": "unverified@example.com",
            "password": "secure-password",
        },
    )

    assert response.status_code in (404, 405)


def test_authenticated_user_submits_pending_post_and_only_mine_lists_it(
    client_and_session,
) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")

    unauthorized_response = client.post(
        "/posts",
        json={"title": "Draft", "content": "This draft has enough text."},
    )
    assert unauthorized_response.status_code == 401

    create_response = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Draft", "content": "This draft has enough text."},
    )

    assert create_response.status_code == 201
    created_post = create_response.json()
    assert created_post["author_id"] == user.id
    assert created_post["status"] == "pending"

    public_response = client.get("/posts")
    assert public_response.status_code == 200
    assert public_response.json() == []

    mine_response = client.get("/posts/mine", headers=authorization_header(user.id))
    assert mine_response.status_code == 200
    assert [post["id"] for post in mine_response.json()] == [created_post["id"]]


def test_post_with_unknown_category_is_rejected(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")

    response = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={
            "title": "Unknown category",
            "content": "This draft has enough text.",
            "category_id": 99999,
        },
    )

    assert response.status_code == 422


def test_admin_can_list_pending_posts_but_regular_user_cannot(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")
    admin = create_user(session_factory, username="admin", role="admin")
    created_post = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Draft", "content": "This draft has enough text."},
    ).json()

    user_response = client.get("/admin/posts", headers=authorization_header(user.id))
    assert user_response.status_code == 403

    admin_response = client.get(
        "/admin/posts?status=pending",
        headers=authorization_header(admin.id),
    )
    assert admin_response.status_code == 200
    assert [post["id"] for post in admin_response.json()] == [created_post["id"]]


def test_published_post_is_visible_in_public_listing(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")
    admin = create_user(session_factory, username="admin", role="admin")
    created_post = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Publish me", "content": "This draft has enough text."},
    ).json()

    review_response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(admin.id),
        json={"status": "published"},
    )
    assert review_response.status_code == 200
    reviewed_post = review_response.json()
    assert reviewed_post["status"] == "published"
    assert reviewed_post["reviewed_by_id"] == admin.id
    assert reviewed_post["reviewed_at"] is not None
    assert reviewed_post["published_at"] is not None

    public_response = client.get("/posts")
    assert public_response.status_code == 200
    public_posts = public_response.json()
    assert [post["id"] for post in public_posts] == [created_post["id"]]
    assert public_posts[0]["status"] == "published"
    assert "review_note" not in public_posts[0]


def test_regular_user_cannot_review_post(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")
    created_post = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Not self-reviewable", "content": "This draft has enough text."},
    ).json()

    response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(user.id),
        json={"status": "published"},
    )

    assert response.status_code == 403


def test_admin_review_of_missing_post_returns_not_found(client_and_session) -> None:
    client, session_factory = client_and_session
    admin = create_user(session_factory, username="admin", role="admin")

    response = client.post(
        "/admin/posts/99999/review",
        headers=authorization_header(admin.id),
        json={"status": "published"},
    )

    assert response.status_code == 404


def test_rejected_post_requires_note_and_stays_private(client_and_session) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")
    admin = create_user(session_factory, username="admin", role="admin")
    created_post = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Needs work", "content": "This draft has enough text."},
    ).json()

    missing_note_response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(admin.id),
        json={"status": "rejected"},
    )
    assert missing_note_response.status_code == 422

    rejected_response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(admin.id),
        json={"status": "rejected", "note": "Please add sources."},
    )
    assert rejected_response.status_code == 200
    assert rejected_response.json()["status"] == "rejected"
    assert rejected_response.json()["review_note"] == "Please add sources."

    mine_response = client.get("/posts/mine", headers=authorization_header(user.id))
    assert mine_response.status_code == 200
    assert mine_response.json()[0]["status"] == "rejected"
    assert mine_response.json()[0]["review_note"] == "Please add sources."

    public_response = client.get("/posts")
    assert public_response.status_code == 200
    assert public_response.json() == []


def test_post_cannot_be_reviewed_twice_and_rejects_server_managed_fields(
    client_and_session,
) -> None:
    client, session_factory = client_and_session
    user = create_user(session_factory, username="author", role="user")
    admin = create_user(session_factory, username="admin", role="admin")

    unknown_fields_response = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={
            "title": "Attempted override",
            "content": "This draft has enough text.",
            "author_id": admin.id,
            "status": "published",
        },
    )
    assert unknown_fields_response.status_code == 422

    created_post = client.post(
        "/posts",
        headers=authorization_header(user.id),
        json={"title": "Review once", "content": "This draft has enough text."},
    ).json()
    first_review_response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(admin.id),
        json={"status": "published"},
    )
    assert first_review_response.status_code == 200

    second_review_response = client.post(
        f"/admin/posts/{created_post['id']}/review",
        headers=authorization_header(admin.id),
        json={"status": "rejected", "note": "Too late."},
    )
    assert second_review_response.status_code == 409
