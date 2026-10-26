"""Optional shared-token auth: bearer header for REST/MCP, signed session cookie + CSRF token for the UI."""

import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Receive, Scope, Send

SESSION_COOKIE = "restfultts_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class LoginRequired(Exception):
    pass


class Auth:
    def __init__(self, token: str) -> None:
        self.token = token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _sign(self, purpose: str, value: str) -> str:
        return hmac.new(self.token.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()

    def check_token(self, candidate: str) -> bool:
        return self.enabled and hmac.compare_digest(candidate.encode(), self.token.encode())

    def check_bearer(self, authorization: str | None) -> bool:
        scheme, _, credentials = (authorization or "").partition(" ")
        return scheme.lower() == "bearer" and self.check_token(credentials.strip())

    def new_session(self) -> str:
        nonce = secrets.token_urlsafe(24)
        return f"{nonce}.{self._sign('session', nonce)}"

    def session_nonce(self, cookie: str | None) -> str | None:
        nonce, _, sig = (cookie or "").partition(".")
        if nonce and hmac.compare_digest(sig, self._sign("session", nonce)):
            return nonce
        return None

    def csrf_token(self, request: Request) -> str:
        nonce = self.session_nonce(request.cookies.get(SESSION_COOKIE))
        return self._sign("csrf", nonce) if self.enabled and nonce else ""

    def ui_ok(self, request: Request) -> bool:
        """Valid UI session; unsafe methods also need the CSRF header or form field."""
        if not self.enabled:
            return True
        nonce = self.session_nonce(request.cookies.get(SESSION_COOKIE))
        if nonce is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return hmac.compare_digest(request.headers.get(CSRF_HEADER, ""), self._sign("csrf", nonce))


def _auth(request: Request) -> Auth:
    auth: Auth = request.app.state.auth
    return auth


def require_api(request: Request) -> None:
    auth = _auth(request)
    if not auth.enabled or auth.check_bearer(request.headers.get("authorization")) or auth.ui_ok(request):
        return
    raise HTTPException(401, "missing or invalid bearer token", headers={"WWW-Authenticate": "Bearer"})


def require_ui(request: Request) -> None:
    if not _auth(request).ui_ok(request):
        raise LoginRequired


class BearerGuard:
    """ASGI wrapper for the MCP endpoint."""

    def __init__(self, app: ASGIApp, auth: Auth) -> None:
        self.app = app
        self.auth = auth

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.auth.enabled:
            headers = dict(scope.get("headers") or [])
            if not self.auth.check_bearer(headers.get(b"authorization", b"").decode("latin-1")):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"detail":"missing or invalid bearer token"}'})
                return
        await self.app(scope, receive, send)
