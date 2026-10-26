# RestfulTTS

Text-to-speech for [PhonixPBX](../phonix) announcements, served over a REST API, an MCP server and a small web UI.

| Language | Voices | Model |
| --- | --- | --- |
| German (`de`) | `thorsten` (neutral) | [Thorsten-Voice/Kokoro](https://huggingface.co/Thorsten-Voice/Kokoro), a Kokoro-82M fine-tune on the CC0 Thorsten-Voice dataset |
| English (`en`) | `af_heart` (default), `af_bella`, `am_michael`, `bf_emma`, `bm_george` | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |
| French (`fr`) | `ff_siwis` | hexgrad/Kokoro-82M |
| Italian (`it`) | `if_sara` (default), `im_nicola` | hexgrad/Kokoro-82M; both voices are only graded "C" by Kokoro |

Inspired by [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts). Unlike that project, it uses the
PyTorch `kokoro` package instead of `kokoro-onnx`, because the German model only exists as a PyTorch checkpoint.
It also needs the [semidark](https://github.com/semidark/kokoro) forks of `kokoro` and `misaki`; only those
forks contain the German G2P.

## Run

With Podman (CPU only), from the released image (linux/amd64 and linux/arm64):

```sh
podman run -d -p 8000:8000 -v restfultts_data:/data ghcr.io/phonixpbx/restfultts:latest
```

Or built from source:

```sh
podman-compose up -d            # or: podman build -t restfultts . && podman run -p 8000:8000 -v restfultts_data:/data restfultts
```

The first start downloads about 650 MB of models and voices into the `/data` volume, which can take several minutes.
Later starts load them from the volume.

Locally with [uv](https://docs.astral.sh/uv/) and Python 3.12:

```sh
uv sync --extra dev
uv run restfultts download          # optional: fetch all models up front
uv run restfultts serve             # http://127.0.0.1:8000
uv run restfultts say "Guten Tag." -o hallo.wav
uv run restfultts say "Buongiorno." -l it -f ulaw -o hallo.ulaw
```

The UI is at `/`, the OpenAPI docs are at `/docs`, and the MCP endpoint is `/mcp`.

## Configuration

Environment variables (or an `.env` file):

| Variable | Default | Description |
| --- | --- | --- |
| `RESTFULTTS_API_TOKEN` | empty | When set, REST and MCP need `Authorization: Bearer <token>` and the UI asks for the token. Empty means open access, so only use that on a trusted network. |
| `RESTFULTTS_DATA_DIR` | `data` (`/data` in the container) | Holds the audio cache. In the container it also holds the models (`HF_HOME=/data/hf`). |
| `RESTFULTTS_PRELOAD` | empty (`de,en,fr,it` in the container) | Languages whose models are loaded at startup; others load on the first request. |
| `RESTFULTTS_DEVICE` | `auto` | `cpu`, `cuda` or `auto`. The container ships CPU-only PyTorch. |
| `RESTFULTTS_THORSTEN_EPOCH` | `5` | Checkpoint of the German model (1–10). |
| `RESTFULTTS_MAX_TEXT_CHARS` | `5000` | Longer texts are rejected with 413. |
| `RESTFULTTS_CACHE_MAX_MB` | `1024` | Size limit of the audio cache; the least recently used files are removed first. |
| `RESTFULTTS_HOST` / `RESTFULTTS_PORT` | `127.0.0.1` / `8000` | Listen address (`0.0.0.0` in the container). |

## REST API

| Method and path | Description |
| --- | --- |
| `POST /api/v1/synthesize` | Body `{"text", "voice"?, "language"?, "speed"? (0.5–2.0), "format"?}`. Returns the audio bytes. Give either `voice` or `language`; with only a language you get its default voice. |
| `GET /api/v1/synthesize?text=…&language=…&format=…` | Same as `POST`, for clients that can only fetch a URL. |
| `GET /api/v1/audio/<hash>.<ext>` | A file from the cache. |
| `DELETE /api/v1/audio/<hash>` | Deletes a file from the cache, with all formats derived from the same synthesis. Returns 204, or 404 if it is not in the cache. |
| `GET /api/v1/voices?language=de`, `/api/v1/languages`, `/api/v1/formats`, `/api/v1/health` | Metadata. |
| `POST /tts` | Compatible with the `thorstenvoice/kokoro-tts` container. `{"text": "..."}` returns German WAV. |

Synthesis responses carry the headers `X-Cache: hit|miss` and `X-Voice`.

Formats:

| Format | Rate | Content |
| --- | --- | --- |
| `wav` | 24 kHz | Original quality |
| `wav16` | 16 kHz | WAV |
| `wav8` | 8 kHz | WAV |
| `sln` | 8 kHz | Asterisk raw signed linear, 16 bit |
| `sln16` | 16 kHz | Asterisk raw signed linear, 16 bit |
| `ulaw` | 8 kHz | Raw G.711 µ-law |
| `alaw` | 8 kHz | Raw G.711 A-law |

The G.711 encoders give the same output as Python's `audioop` for every 16-bit sample.

```sh
curl -o ansage.wav -H 'Content-Type: application/json' \
     -d '{"text": "Guten Tag und willkommen."}' http://localhost:8000/tts
curl -o ansage.ulaw 'http://localhost:8000/api/v1/synthesize?text=Benvenuti&language=it&format=ulaw'
```

Each text is synthesized once and cached as 24 kHz WAV. Other formats of the same text are derived from that file.

## MCP

The MCP endpoint uses Streamable HTTP (stateless, JSON responses) at `http://<host>:8000/mcp`. If a token is
configured, clients send it as a bearer token. It offers three tools:

- `list_voices(language?)`
- `list_formats()`
- `delete_audio(url)` deletes a file and all its formats.
- `synthesize(text, voice?, language?, speed?, format?)` returns the audio as MCP audio content, plus a JSON text
  with the voice, the duration and the download path.

```sh
claude mcp add --transport http restfultts http://localhost:8000/mcp --header "Authorization: Bearer $TOKEN"
```

## Development

```sh
uv run pytest -q                    # unit, API, MCP and UI tests with a fake engine
uv run pytest -m models             # real synthesis in all four languages (downloads the models)
uv run ruff check . && uv run ruff format --check . && uv run mypy src
scripts/test-container.sh <image>   # smoke test of a built image, as in CI
scripts/vendor-update.sh            # refresh Tabler 1.7.1 / htmx 4.0.0 (same versions as PhonixPBX)
```

Releases are tagged `vX.Y.Z`. CI then builds and pushes the container image and creates the GitHub release from
`CHANGELOG.md`; see [docs/RELEASING.md](docs/RELEASING.md).

## Licenses

RestfulTTS is licensed under Apache-2.0. Both models are Apache-2.0, and the Thorsten-Voice dataset is CC0.

For phonemization, `misaki` uses espeak-ng through `phonemizer-fork` and `espeakng-loader`. Both are GPL-3 and are
installed as unmodified Python dependencies. Unlike in PhonixPBX, espeak-ng does not produce the speech here; it only
converts text to phonemes for Kokoro. See [NOTICE](NOTICE).
