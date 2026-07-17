from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = PROJECT_ROOT / "public"


def read_public_file(relative_path: str) -> str:
    return (PUBLIC_DIR / relative_path).read_text(encoding="utf-8")


def test_content_workflow_pages_are_present() -> None:
    assert (PUBLIC_DIR / "submit.html").is_file()
    assert (PUBLIC_DIR / "my-posts.html").is_file()


def test_public_pages_do_not_keep_legacy_identity_or_sample_content() -> None:
    for relative_path in ("index.html", "dashboard.html"):
        page = read_public_file(relative_path)
        assert "2191737256@qq.com" not in page
        assert "青铜与火之王苏醒预警分析报告" not in page


def test_frontend_never_uses_innerhtml_for_dynamic_content() -> None:
    public_sources = [
        *PUBLIC_DIR.glob("*.html"),
        *PUBLIC_DIR.rglob("*.js"),
    ]

    for source in public_sources:
        assert "innerHTML" not in source.read_text(encoding="utf-8"), source


def test_api_helper_covers_content_moderation_contract() -> None:
    api = read_public_file("js/api.js")

    for endpoint in (
        "/auth/login",
        "/auth/logout",
        "/auth/me",
        "/posts",
        "/posts/mine",
        "/admin/posts?status=pending",
        "/admin/posts/${postId}/review",
    ):
        assert endpoint in api

    assert '"https://api.solocraft.xyz"' in api
    assert "formatApiError" in api
    assert "window.blogApi" in api


def test_api_helper_includes_cross_subdomain_cookie_sessions_without_browser_token_storage() -> None:
    api = read_public_file("js/api.js")

    assert "localStorage" not in api
    assert "Authorization" not in api
    assert 'credentials: "include"' in api
    assert "error.status = response.status" in api


def test_dashboard_checks_server_identity_before_loading_admin_posts() -> None:
    dashboard = read_public_file("dashboard.html")

    assert "blogApi.getCurrentUser()" in dashboard
    assert "blogApi.getPendingPosts()" in dashboard
    assert "blogApi.reviewPost(" in dashboard
    assert "localStorage.getItem(\"user_role\")" not in dashboard
    assert "current_user" not in dashboard


def test_dashboard_refresh_button_reloads_pending_posts_with_loading_state() -> None:
    dashboard = read_public_file("dashboard.html")

    assert dashboard.count('id="refresh-pending-button"') == 1
    assert ">刷新待审列表<" in dashboard
    assert 'refreshButton.addEventListener("click", loadPendingPosts);' in dashboard
    assert "refreshButton.disabled = true;" in dashboard
    assert "finally" in dashboard


def test_dashboard_refresh_button_starts_disabled() -> None:
    dashboard = read_public_file("dashboard.html")

    assert re.search(
        r'<button[^>]*id="refresh-pending-button"[^>]*\bdisabled\b',
        dashboard,
    )


def test_protected_pages_redirect_unauthenticated_users_to_login() -> None:
    for relative_path in ("submit.html", "my-posts.html", "dashboard.html"):
        page = read_public_file(relative_path)
        assert "error.status === 401" in page
        assert 'window.location.replace("login.html")' in page


def test_dashboard_only_enables_refresh_after_server_confirms_admin() -> None:
    dashboard = read_public_file("dashboard.html")

    assert 'if (!user || user.role !== "admin")' in dashboard
    assert 'window.location.replace("index.html")' in dashboard
    assert dashboard.index('if (!user || user.role !== "admin")') < dashboard.index(
        "refreshButton.disabled = false;"
    )


def test_html_pages_do_not_contain_legacy_browser_authentication_state() -> None:
    html_files = [
        PROJECT_ROOT / "index.html",
        PROJECT_ROOT / "login.html",
        PROJECT_ROOT / "dashboard.html",
        *PUBLIC_DIR.glob("*.html"),
    ]

    for source in html_files:
        page = source.read_text(encoding="utf-8")
        assert "localStorage" not in page, source
        assert "current_user" not in page, source
        assert "2191737256@qq.com" not in page, source


def test_root_legacy_pages_redirect_to_the_cookie_session_pages() -> None:
    for filename in ("index.html", "login.html", "dashboard.html"):
        page = (PROJECT_ROOT / filename).read_text(encoding="utf-8")
        assert f'window.location.replace("public/{filename}")' in page
