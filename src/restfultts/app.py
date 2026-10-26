"""FastAPI application factory."""

import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route

from . import __version__, api, ui
from .auth import Auth, BearerGuard, LoginRequired
from .cache import AudioCache
from .config import Settings, get_settings
from .engine import Engine, KokoroEngine
from .mcp_server import build_mcp
from .service import TTSService

log = logging.getLogger(__name__)

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    # Tabler and htmx set inline styles
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "media-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
# FastAPI's /docs page loads Swagger UI from a CDN and runs an inline script
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com"
)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or KokoroEngine(device=settings.device, thorsten_epoch=settings.thorsten_epoch)
    service = TTSService(engine, AudioCache(settings.cache_dir, settings.cache_max_mb), settings.max_text_chars)
    auth = Auth(settings.api_token)
    mcp = build_mcp(service)
    # Builds the session manager; our own route below serves it so that /mcp needs no redirect to /mcp/.
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # the service is meant to be reached by other hosts; protect it with RESTFULTTS_API_TOKEN instead
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp_endpoint = next(r for r in mcp_app.routes if isinstance(r, Route)).app

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.preload_languages:
            log.info("preloading %s", ", ".join(settings.preload_languages))
            await anyio.to_thread.run_sync(engine.preload, settings.preload_languages)
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="RestfulTTS",
        description="Kokoro text-to-speech for PhonixPBX: de (Thorsten), en, fr, it.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.service = service
    app.state.auth = auth

    app.include_router(api.router)
    app.include_router(ui.public)
    app.include_router(ui.router)
    app.router.routes.append(Route("/mcp", endpoint=BearerGuard(mcp_endpoint, auth), methods=["GET", "POST", "DELETE"]))
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    ui.templates.env.globals["max_text_chars"] = settings.max_text_chars

    @app.exception_handler(LoginRequired)
    async def login_required(request: Request, exc: LoginRequired) -> Response:
        if request.headers.get("HX-Request"):
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", 303)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        is_docs = request.url.path in ("/docs", "/redoc")
        response.headers.setdefault("Content-Security-Policy", DOCS_CSP if is_docs else CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    return app
