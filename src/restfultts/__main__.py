"""Command line: ``restfultts serve|download|say``."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import get_settings
from .voices import LANGUAGES


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "restfultts.app:create_app",
        factory=True,
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
        proxy_headers=True,
        forwarded_allow_ips="*" if args.behind_proxy else None,
    )
    return 0


def _download(args: argparse.Namespace) -> int:
    from .engine import KokoroEngine

    settings = get_settings()
    languages = args.languages or list(LANGUAGES)
    KokoroEngine(device="cpu", thorsten_epoch=settings.thorsten_epoch).preload(languages)
    print(f"models and voices for {', '.join(languages)} are in the Hugging Face cache")
    return 0


def _say(args: argparse.Namespace) -> int:
    from .cache import AudioCache
    from .engine import KokoroEngine
    from .service import RequestError, TTSService

    settings = get_settings()
    engine = KokoroEngine(device=settings.device, thorsten_epoch=settings.thorsten_epoch)
    service = TTSService(engine, AudioCache(settings.cache_dir, settings.cache_max_mb), settings.max_text_chars)
    try:
        req = service.build_request(args.text, args.voice, args.language, args.speed, args.format)
    except RequestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result = asyncio.run(service.synthesize(req))
    out = Path(args.output or result.filename)
    out.write_bytes(result.entry.path.read_bytes())
    print(out)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="restfultts", description="Kokoro text-to-speech service")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the HTTP server (REST, MCP, UI)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--reload", action="store_true", help="reload on code changes (development)")
    p.add_argument("--behind-proxy", action="store_true", help="trust X-Forwarded-* headers from any address")
    p.set_defaults(func=_serve)

    p = sub.add_parser("download", help="fetch models and voices into the Hugging Face cache")
    p.add_argument("languages", nargs="*", choices=list(LANGUAGES), help="default: all")
    p.set_defaults(func=_download)

    p = sub.add_parser("say", help="synthesize one text into a file")
    p.add_argument("text")
    p.add_argument("-l", "--language", default=None)
    p.add_argument("-v", "--voice", default=None)
    p.add_argument("-s", "--speed", type=float, default=1.0)
    p.add_argument("-f", "--format", default="wav")
    p.add_argument("-o", "--output")
    p.set_defaults(func=_say)

    args = parser.parse_args()
    if args.command == "say" and not (args.voice or args.language):
        args.language = "de"
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
