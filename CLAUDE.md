# CLAUDE.md

RestfulTTS is a Kokoro text-to-speech service for PhonixPBX: FastAPI (REST + web UI) and an MCP server in one
process, Python 3.12. The user-facing docs are in `README.md`.

## Commands

```sh
uv sync --extra dev
uv run pytest -q                    # fast tests, FakeEngine (no models)
uv run pytest -m models             # real Kokoro synthesis, downloads ~650 MB on first run
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run restfultts serve --reload
podman build -t restfultts . && scripts/test-container.sh restfultts   # image smoke test (as in CI)
scripts/release.sh check vX.Y.Z      # tag, version files and CHANGELOG agree
```

## CI and releases

- `.github/workflows/ci.yml` runs ruff, mypy, pytest, shellcheck and the vendor checksums on pushes to `main` and on
  pull requests.
- `.github/workflows/container.yml` builds the image and runs `scripts/test-container.sh`.
  - nightly or manual: pushes `edge`
  - `v*` tag: pushes `<version>` (+ `latest` for final releases) and creates the GitHub release
  - pull request: builds and tests only
- The procedure is in `docs/RELEASING.md`. The version lives in `pyproject.toml` and `src/restfultts/__init__.py`
  (PEP 440, `X.Y.Z.dev0` between releases).

## Architecture

- `voices.py`: the static voice table. A voice maps to a model (`base` = hexgrad/Kokoro-82M, `thorsten` =
  Thorsten-Voice/Kokoro) and a KPipeline `lang_code`. A new voice needs a row here; a new language also needs
  `LANGUAGES` and `DEFAULT_VOICE`.
- `engine.py`: `KokoroEngine` loads models and pipelines lazily and serializes inference per model with a lock.
  Text is pre-split by `split_text`, because Kokoro truncates chunks at 510 phonemes. The German pipeline patches
  its G2P (`ʏ`→`y`), as the model card says. `FakeEngine` is used in tests through `create_app(settings, engine)`.
- `service.py`: validation → cache → engine → encode. The 24 kHz WAV is the cached master, and other formats are
  derived from it. Errors are `RequestError` (422) and `TextTooLong` (413). REST, MCP and UI all go through
  `TTSService`.
- `audio.py`: resampling with soxr and the format table. The G.711 encoders are tested bit-exact against `audioop`.
- `cache.py`: sha256-keyed files under `<data>/cache/xx/`, each with a `.json` sidecar, pruned LRU by size.
- `auth.py`: one optional shared token. REST and MCP use a bearer header; the UI uses a signed session cookie plus
  an `X-CSRF-Token` header that `static/app.js` adds to every htmx request.
- `app.py`: the `/mcp` route is the MCP SDK's ASGI endpoint wrapped in `BearerGuard`. The SDK is mcp 2.x
  (`MCPServer`, not `FastMCP`), and its session manager runs in the FastAPI lifespan.
- UI: Jinja templates and htmx 4. htmx 4 attributes are not inherited implicitly, and it swaps 4xx responses too.
  Error partials therefore return 422. The CSP forbids inline scripts, so behaviour goes in `static/app.js`
  through `data-*` attributes.

## Conventions

- Commit messages: `area: lowercase summary`.
- User-visible changes get a `CHANGELOG.md` entry under `## [Unreleased]`.
- Ruff line length is 120.
- `kokoro` and `misaki` come from the semidark forks, pinned to commits in `pyproject.toml`. Both cap Python
  at `<3.14`.
