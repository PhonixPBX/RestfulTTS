"""REST API (/api/v1) and the legacy POST /tts endpoint."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .audio import FORMATS
from .auth import require_api
from .service import MAX_SPEED, MIN_SPEED, RequestError, Result, TTSService
from .voices import LANGUAGES, voices_for

router = APIRouter(dependencies=[Depends(require_api)])


class SynthesizeBody(BaseModel):
    text: str = Field(description="Text to speak")
    voice: str | None = Field(None, description="Voice id, see /api/v1/voices; wins over language")
    language: str | None = Field(None, description="de, en, fr or it; picks the language's default voice")
    speed: float = Field(1.0, ge=MIN_SPEED, le=MAX_SPEED)
    format: str = Field("wav", description="Audio format, see /api/v1/formats")


def _service(request: Request) -> TTSService:
    service: TTSService = request.app.state.service
    return service


ServiceDep = Annotated[TTSService, Depends(_service)]


def _audio_response(result: Result) -> FileResponse:
    return FileResponse(
        result.entry.path,
        media_type=result.format.content_type,
        filename=result.filename,
        headers={"X-Cache": "hit" if result.cache_hit else "miss", "X-Voice": result.voice.id},
    )


async def _synthesize(service: TTSService, body: SynthesizeBody) -> FileResponse:
    try:
        req = service.build_request(body.text, body.voice, body.language, body.speed, body.format)
    except RequestError as e:
        raise HTTPException(e.status_code, str(e)) from None
    return _audio_response(await service.synthesize(req))


@router.get("/api/v1/health", tags=["meta"])
def health(service: ServiceDep) -> dict[str, Any]:
    return {"status": "ok", "engine": service.engine.revision, "loaded_models": service.engine.loaded()}


@router.get("/api/v1/languages", tags=["meta"])
def languages() -> dict[str, str]:
    return LANGUAGES


@router.get("/api/v1/voices", tags=["meta"])
def voices(language: str | None = None) -> list[dict[str, Any]]:
    if language and language not in LANGUAGES:
        raise HTTPException(422, f"unknown language {language!r}")
    return [v.as_dict() for v in voices_for(language)]


@router.get("/api/v1/formats", tags=["meta"])
def formats() -> list[dict[str, Any]]:
    return [
        {"name": f.name, "rate": f.rate, "content_type": f.content_type, "ext": f.ext, "description": f.description}
        for f in FORMATS.values()
    ]


@router.post("/api/v1/synthesize", tags=["tts"], response_class=Response)
async def synthesize(body: SynthesizeBody, service: ServiceDep) -> FileResponse:
    """Synthesize text; returns the audio bytes in the requested format."""
    return await _synthesize(service, body)


@router.get("/api/v1/synthesize", tags=["tts"], response_class=Response)
async def synthesize_get(service: ServiceDep, params: Annotated[SynthesizeBody, Query()]) -> FileResponse:
    """Same as POST, for clients that can only fetch a URL."""
    return await _synthesize(service, params)


@router.get("/api/v1/audio/{name}", tags=["tts"], response_class=Response)
def audio(name: str, service: ServiceDep) -> FileResponse:
    """A previously synthesized file from the cache, by the ``url`` a synthesis returned."""
    key, _, ext = name.partition(".")
    entry = service.cache.get(key, ext)
    fmt = next((f for f in FORMATS.values() if f.ext == ext), None)
    if entry is None or fmt is None:
        raise HTTPException(404, "not in cache")
    return FileResponse(entry.path, media_type=fmt.content_type)


@router.delete("/api/v1/audio/{key}", tags=["tts"], status_code=204, response_class=Response)
def delete_audio(key: str, service: ServiceDep) -> Response:
    """Delete a cached file and all formats derived from the same synthesis; ``key`` may carry an extension."""
    if not service.cache.delete(key.partition(".")[0]):
        raise HTTPException(404, "not in cache")
    return Response(status_code=204)


@router.post("/tts", tags=["legacy"], response_class=Response)
async def legacy_tts(body: SynthesizeBody, service: ServiceDep) -> FileResponse:
    """Compatible with the thorstenvoice/kokoro-tts container: ``{"text": ...}`` in, German WAV out."""
    if not body.voice and not body.language:
        body.language = "de"
    return await _synthesize(service, body)
