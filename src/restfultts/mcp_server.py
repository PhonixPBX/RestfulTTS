"""MCP tools (Streamable HTTP at /mcp)."""

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.utilities.types import Audio
from mcp.types import AudioContent, TextContent

from .audio import FORMATS
from .service import RequestError, TTSService
from .voices import LANGUAGES, voices_for

INSTRUCTIONS = """Text-to-speech with Kokoro for PBX announcements.
Languages: de (Thorsten), en, fr, it. Call list_voices first if you need a specific voice;
otherwise pass a language and its default voice is used. Telephony formats: wav8, sln, ulaw, alaw."""


def build_mcp(service: TTSService) -> MCPServer:
    mcp = MCPServer("RestfulTTS", instructions=INSTRUCTIONS)

    @mcp.tool()
    def list_voices(language: str | None = None) -> list[dict[str, Any]]:
        """List the available voices, optionally only those of one language (de, en, fr, it)."""
        if language and language not in LANGUAGES:
            raise ToolError(f"unknown language {language!r}, use one of {', '.join(LANGUAGES)}")
        return [v.as_dict() for v in voices_for(language)]

    @mcp.tool()
    def list_formats() -> list[dict[str, Any]]:
        """List the audio formats synthesize can return."""
        return [
            {"name": f.name, "rate": f.rate, "content_type": f.content_type, "description": f.description}
            for f in FORMATS.values()
        ]

    @mcp.tool(structured_output=False)
    async def synthesize(
        text: str,
        voice: str | None = None,
        language: str | None = None,
        speed: float = 1.0,
        format: str = "wav",
    ) -> list[AudioContent | TextContent]:
        """Turn text into speech. Give a voice id or a language; speed 0.5-2.0; format e.g. wav, wav8, ulaw.

        Returns the audio and a JSON summary with the download path (relative to this server)."""
        try:
            result = await service.synthesize(service.build_request(text, voice, language, speed, format))
        except RequestError as e:
            raise ToolError(str(e)) from None
        info = {
            "voice": result.voice.id,
            "language": result.voice.language,
            "format": result.format.name,
            "content_type": result.format.content_type,
            "duration": result.entry.meta.get("duration"),
            "cache_hit": result.cache_hit,
            "url": result.url,
        }
        audio = Audio(data=result.entry.path.read_bytes()).to_audio_content()
        audio.mime_type = result.format.content_type
        return [audio, TextContent(type="text", text=json.dumps(info))]

    @mcp.tool()
    def delete_audio(url: str) -> str:
        """Delete a synthesized file and all its formats, by the url (or hash) synthesize returned."""
        key = url.rstrip("/").rpartition("/")[2].partition(".")[0]
        if not service.cache.delete(key):
            raise ToolError(f"{url!r} is not in the cache")
        return "deleted"

    return mcp
