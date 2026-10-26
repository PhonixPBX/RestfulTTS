"""Content-addressed file cache for synthesized audio."""

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_HASH_CHARS = set("0123456789abcdef")


@dataclass(frozen=True)
class Entry:
    key: str
    path: Path
    meta: dict[str, Any]


def cache_key(revision: str, voice: str, speed: float, fmt: str, text: str) -> str:
    raw = json.dumps([revision, voice, round(speed, 2), fmt, text], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class AudioCache:
    def __init__(self, root: Path, max_mb: int) -> None:
        self.root = root
        self.max_bytes = max_mb * 1024 * 1024

    def _paths(self, key: str, ext: str) -> tuple[Path, Path]:
        d = self.root / key[:2]
        return d / f"{key}.{ext}", d / f"{key}.json"

    def get(self, key: str, ext: str) -> Entry | None:
        if not (len(key) == 64 and set(key) <= _HASH_CHARS and ext.isalnum()):
            return None
        audio, meta = self._paths(key, ext)
        if not audio.is_file():
            return None
        try:
            info = json.loads(meta.read_text("utf-8"))
        except (OSError, ValueError):
            info = {}
        os.utime(audio)  # LRU: touch on read
        return Entry(key, audio, info)

    def put(self, key: str, ext: str, data: bytes, meta: dict[str, Any]) -> Entry:
        audio, meta_path = self._paths(key, ext)
        audio.parent.mkdir(parents=True, exist_ok=True)
        meta = {**meta, "key": key, "ext": ext, "size": len(data), "created": time.time()}
        _write_atomic(meta_path, json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        _write_atomic(audio, data)
        self.prune()
        return Entry(key, audio, meta)

    def delete(self, key: str) -> int:
        """Remove an entry and every entry derived from it (``meta["master"] == key``); returns the files removed."""
        if not (len(key) == 64 and set(key) <= _HASH_CHARS) or not self.root.is_dir():
            return 0
        keys = {key}
        for meta_path in self.root.glob("??/*.json"):
            try:
                if json.loads(meta_path.read_text("utf-8")).get("master") == key:
                    keys.add(meta_path.stem)
            except (OSError, ValueError):
                continue
        removed = 0
        for k in keys:
            for path in (self.root / k[:2]).glob(f"{k}.*"):
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def _audio_files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [p for p in self.root.glob("??/*") if p.suffix != ".json" and not p.name.startswith(".")]

    def prune(self) -> None:
        files = sorted(self._audio_files(), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        while files and total > self.max_bytes:
            victim = files.pop(0)
            total -= victim.stat().st_size
            victim.unlink(missing_ok=True)
            victim.with_suffix(".json").unlink(missing_ok=True)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        metas = []
        for meta_path in self.root.glob("??/*.json") if self.root.is_dir() else []:
            try:
                meta = json.loads(meta_path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if meta_path.with_suffix(f".{meta.get('ext')}").is_file():
                metas.append(meta)
        metas.sort(key=lambda m: m.get("created", 0), reverse=True)
        return metas[:limit]
