"""Synthesis use case shared by REST, MCP and the UI.

Every text is synthesized once and cached as 24 kHz WAV (the master); other formats are derived from it.
"""

import io
from dataclasses import dataclass

import anyio
import numpy as np
import soundfile as sf

from .audio import FORMATS, SAMPLE_RATE, AudioFormat, encode
from .cache import AudioCache, Entry, cache_key
from .engine import Engine
from .voices import Voice, VoiceError, resolve

MASTER = FORMATS["wav"]
MIN_SPEED, MAX_SPEED = 0.5, 2.0


class RequestError(ValueError):
    status_code = 422


class TextTooLong(RequestError):
    status_code = 413


@dataclass(frozen=True)
class Request:
    text: str
    voice: Voice
    speed: float
    format: AudioFormat


@dataclass(frozen=True)
class Result:
    entry: Entry
    voice: Voice
    format: AudioFormat
    cache_hit: bool

    @property
    def url(self) -> str:
        return f"/api/v1/audio/{self.entry.key}.{self.format.ext}"

    @property
    def filename(self) -> str:
        return f"tts-{self.entry.key[:12]}.{self.format.ext}"


class TTSService:
    def __init__(self, engine: Engine, cache: AudioCache, max_text_chars: int) -> None:
        self.engine = engine
        self.cache = cache
        self.max_text_chars = max_text_chars

    def build_request(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
        speed: float = 1.0,
        format: str = "wav",
    ) -> Request:
        text = text.strip()
        if not text:
            raise RequestError("text is empty")
        if len(text) > self.max_text_chars:
            raise TextTooLong(f"text is longer than {self.max_text_chars} characters")
        if not MIN_SPEED <= speed <= MAX_SPEED:
            raise RequestError(f"speed must be between {MIN_SPEED} and {MAX_SPEED}")
        try:
            fmt = FORMATS[format]
        except KeyError:
            raise RequestError(f"unknown format {format!r}, use one of {', '.join(FORMATS)}") from None
        try:
            resolved = resolve(voice, language)
        except VoiceError as e:
            raise RequestError(str(e)) from None
        return Request(text, resolved, round(speed, 2), fmt)

    def _key(self, req: Request, fmt: AudioFormat) -> str:
        return cache_key(self.engine.revision, req.voice.id, req.speed, fmt.name, req.text)

    def _meta(self, req: Request, fmt: AudioFormat) -> dict[str, object]:
        return {
            "text": req.text,
            "voice": req.voice.id,
            "language": req.voice.language,
            "speed": req.speed,
            "format": fmt.name,
        }

    async def _master(self, req: Request) -> tuple[Entry, bool]:
        key = self._key(req, MASTER)
        if entry := self.cache.get(key, MASTER.ext):
            return entry, True
        samples = await anyio.to_thread.run_sync(self.engine.synthesize, req.text, req.voice, req.speed)
        meta = {**self._meta(req, MASTER), "duration": round(len(samples) / SAMPLE_RATE, 2)}
        return self.cache.put(key, MASTER.ext, encode(samples, MASTER), meta), False

    async def synthesize(self, req: Request) -> Result:
        master, hit = await self._master(req)
        if req.format is MASTER:
            return Result(master, req.voice, MASTER, hit)
        key = self._key(req, req.format)
        if entry := self.cache.get(key, req.format.ext):
            return Result(entry, req.voice, req.format, True)
        samples, _ = sf.read(io.BytesIO(master.path.read_bytes()), dtype="float32")
        data = encode(np.asarray(samples), req.format)
        meta = {**self._meta(req, req.format), "duration": master.meta.get("duration"), "master": master.key}
        return Result(self.cache.put(key, req.format.ext, data, meta), req.voice, req.format, hit)

    def history(self, limit: int = 20) -> list[dict[str, object]]:
        return [m for m in self.cache.recent(limit * 4) if m.get("format") == MASTER.name][:limit]
