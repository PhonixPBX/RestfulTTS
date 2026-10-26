"""Web UI: full pages plus htmx partials."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .audio import FORMATS
from .auth import SESSION_COOKIE, require_ui
from .service import MAX_SPEED, MIN_SPEED, RequestError, TTSService
from .voices import DEFAULT_VOICE, LANGUAGES, voices_for

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

public = APIRouter(include_in_schema=False)
router = APIRouter(include_in_schema=False, dependencies=[Depends(require_ui)])


def _service(request: Request) -> TTSService:
    service: TTSService = request.app.state.service
    return service


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    auth = request.app.state.auth
    context |= {"auth_enabled": auth.enabled, "csrf_token": auth.csrf_token(request)}
    return templates.TemplateResponse(request, name, context, status_code=status_code)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return render(
        request,
        "index.html",
        languages=LANGUAGES,
        language="de",
        voices=voices_for("de"),
        selected_voice=DEFAULT_VOICE["de"],
        formats=FORMATS.values(),
        min_speed=MIN_SPEED,
        max_speed=MAX_SPEED,
        history=_service(request).history(),
    )


@router.get("/ui/voices", response_class=HTMLResponse)
def voices_partial(request: Request, language: str = "de") -> HTMLResponse:
    if language not in LANGUAGES:
        language = "de"
    return render(
        request,
        "partials/voices_select.html",
        voices=voices_for(language),
        selected_voice=DEFAULT_VOICE[language],
    )


@router.post("/ui/synthesize", response_class=HTMLResponse)
async def synthesize_partial(
    request: Request,
    text: Annotated[str, Form()] = "",
    voice: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "",
    speed: Annotated[float, Form()] = 1.0,
    format: Annotated[str, Form()] = "wav",
) -> HTMLResponse:
    service = _service(request)
    try:
        req = service.build_request(text, voice or None, language or None, speed, format)
        result = await service.synthesize(req)
        # browsers cannot play raw telephony formats; the 24 kHz master is always cached, so this is cheap
        preview = await service.synthesize(service.build_request(text, req.voice.id, None, speed, "wav"))
    except RequestError as e:
        return render(request, "partials/error.html", status_code=e.status_code, message=str(e))
    response = render(request, "partials/result.html", result=result, preview=preview)
    response.headers["HX-Trigger"] = "history-changed"
    return response


@router.get("/ui/history", response_class=HTMLResponse)
def history_partial(request: Request) -> HTMLResponse:
    return render(request, "partials/history.html", history=_service(request).history())


@router.delete("/ui/audio/{key}", response_class=HTMLResponse)
def delete_partial(request: Request, key: str) -> HTMLResponse:
    service = _service(request)
    service.cache.delete(key)
    return render(request, "partials/history.html", history=service.history())


@public.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    if not request.app.state.auth.enabled:
        return RedirectResponse("/", 303)
    return render(request, "login.html", error=None)


@public.post("/login", response_class=HTMLResponse)
def login(request: Request, token: Annotated[str, Form()] = "") -> Response:
    auth = request.app.state.auth
    if not auth.check_token(token):
        return render(request, "login.html", status_code=401, error="Invalid token.")
    response = RedirectResponse("/", 303)
    secure = request.url.scheme == "https"
    response.set_cookie(SESSION_COOKIE, auth.new_session(), httponly=True, samesite="strict", secure=secure)
    return response


@public.post("/logout")
def logout() -> Response:
    response = RedirectResponse("/login", 303)
    response.delete_cookie(SESSION_COOKIE)
    return response
