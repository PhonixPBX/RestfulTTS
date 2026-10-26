# Changelog

All notable changes to RestfulTTS are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Text-to-speech with Kokoro-82M (English, French, Italian) and the Thorsten-Voice fine-tune (German).
- REST API under `/api/v1` with WAV (24/16/8 kHz) and the telephony formats `sln`, `sln16`, `ulaw` and `alaw`;
  `POST /tts` stays compatible with the `thorstenvoice/kokoro-tts` container.
- MCP server at `/mcp` (Streamable HTTP) with the tools `list_voices`, `list_formats` and `synthesize`.
- Web UI (Tabler + htmx) with playback, download and history.
- Container image `ghcr.io/phonixpbx/restfultts` for linux/amd64 and linux/arm64: `<version>` and `latest` for
  releases, `edge` for the latest build of `main`.
- Optional bearer token (`RESTFULTTS_API_TOKEN`) for REST, MCP and the UI login.
- `RESTFULTTS_ALLOWED_HOSTS` limits the host names the server answers to; on loopback only `localhost` and
  `127.0.0.1` are accepted by default, against DNS rebinding.
- File cache keyed by text, voice, speed and format. Entries can be deleted with the trash button in the history,
  `DELETE /api/v1/audio/<hash>` or the MCP tool `delete_audio`; this removes all formats of that synthesis.
