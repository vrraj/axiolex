"""ASGI boundary tests for Axiolex shared bearer authentication."""

import base64

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from axiolex.core.config import ServerConfig
from axiolex.security import InboundAuthMiddleware, OperatorSessionStore


def _token() -> str:
    return base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")


def _app() -> TestClient:
    app = FastAPI()

    @app.get("/health/live")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected(request: Request):
        return {"authorization_seen": "authorization" in request.headers}

    async def mcp_endpoint(request):
        return JSONResponse({"method": request.method})

    app.mount("/mcp", FastAPI(routes=[Route("/", mcp_endpoint, methods=["GET", "POST", "DELETE"])]))
    app.add_middleware(
        InboundAuthMiddleware,
        server=ServerConfig(auth_mode="static", api_bearer_token=_token()),
    )
    return TestClient(app)


def test_only_minimal_liveness_is_anonymous():
    with _app() as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic nope"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer wrong"},
        [("Authorization", f"Bearer {_token()}"), ("Authorization", f"Bearer {_token()}")],
    ],
)
def test_static_mode_rejects_missing_malformed_or_duplicate_authorization(headers):
    with _app() as client:
        response = client.get("/protected", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Authentication required: provide a valid bearer token."}


def test_query_and_cookie_credentials_are_not_accepted():
    with _app() as client:
        query = client.get(f"/protected?access_token={_token()}")
        cookie = client.get("/protected", cookies={"access_token": _token()})
        body = client.post("/mcp/", json={"access_token": _token()})

    assert query.status_code == cookie.status_code == body.status_code == 401


@pytest.mark.parametrize("path", ["/protected/", "/%70rotected"])
def test_path_normalization_does_not_bypass_authentication(path):
    with _app() as client:
        response = client.get(path)

    assert response.status_code == 401


def test_valid_bearer_reaches_rest_but_is_not_exposed_to_application_code():
    with _app() as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {_token()}"})

    assert response.status_code == 200
    assert response.json() == {"authorization_seen": False}


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_mounted_mcp_methods_are_authenticated_before_routing(method):
    with _app() as client:
        unauthenticated = getattr(client, method)("/mcp/")
        authenticated = getattr(client, method)(
            "/mcp/", headers={"Authorization": f"Bearer {_token()}"}
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    assert unauthenticated.json() == {"detail": "Access denied: missing or invalid bearer token."}
    assert authenticated.status_code == 200
    assert authenticated.json() == {"method": method.upper()}


@pytest.mark.parametrize("path", ["/", "/docs/search-help.html", "/static/assets/app.js"])
def test_unauthenticated_browser_navigation_redirects_to_login(path):
    with _app() as client:
        response = client.get(path, headers={"Accept": "text/html"}, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_unauthenticated_mcp_browser_navigation_still_returns_bearer_denial():
    with _app() as client:
        response = client.get("/mcp/", headers={"Accept": "text/html"}, follow_redirects=False)

    assert response.status_code == 401
    assert response.json() == {"detail": "Access denied: missing or invalid bearer token."}


def test_options_is_not_a_preflight_bypass_without_explicit_cors_configuration():
    with _app() as client:
        response = client.options("/protected")

    assert response.status_code == 401


def test_operator_session_allows_reads_but_requires_same_origin_csrf_for_writes():
    sessions = OperatorSessionStore()
    session_id, csrf_token = sessions.create()
    app = FastAPI()

    @app.api_route("/admin", methods=["GET", "POST"])
    async def admin():
        return {"ok": True}

    app.add_middleware(
        InboundAuthMiddleware,
        server=ServerConfig(auth_mode="static", api_bearer_token=_token()),
        sessions=sessions,
    )
    with TestClient(app, base_url="http://axiolex.test") as client:
        client.cookies.set("axiolex_session", session_id)
        read = client.get("/admin")
        missing_csrf = client.post("/admin", headers={"Origin": "http://axiolex.test"})
        wrong_origin = client.post("/admin", headers={"X-CSRF-Token": csrf_token, "Origin": "http://evil.test"})
        write = client.post("/admin", headers={"X-CSRF-Token": csrf_token, "Origin": "http://axiolex.test"})

    assert read.status_code == write.status_code == 200
    assert missing_csrf.status_code == wrong_origin.status_code == 401


def test_operator_session_allows_mcp_provider_management_but_not_mcp_endpoint():
    sessions = OperatorSessionStore()
    session_id, _ = sessions.create()
    app = FastAPI()

    @app.get("/mcp-providers")
    async def providers():
        return {"providers": []}

    async def mcp_endpoint(request):
        return JSONResponse({"method": request.method})

    app.mount("/mcp", FastAPI(routes=[Route("/", mcp_endpoint, methods=["GET"])]))
    app.add_middleware(
        InboundAuthMiddleware,
        server=ServerConfig(auth_mode="static", api_bearer_token=_token()),
        sessions=sessions,
    )
    with TestClient(app) as client:
        client.cookies.set("axiolex_session", session_id)
        providers_response = client.get("/mcp-providers")
        mcp_response = client.get("/mcp/")

    assert providers_response.status_code == 200
    assert mcp_response.status_code == 401
