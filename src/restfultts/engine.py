"""Speech synthesis engines: Kokoro (two models) and a fake one for tests."""

import logging
import re
import threading
from typing import Any, Protocol

import numpy as np

from .audio import SAMPLE_RATE
from .voices import LANGUAGES, ModelName, Voice, voices_for

log = logging.getLogger(__name__)

BASE_REPO = "hexgrad/Kokoro-82M"
THORSTEN_REPO = "Thorsten-Voice/Kokoro"
# Kokoro truncates a chunk at 510 phonemes; this many characters stay safely below that.
CHUNK_CHARS = 250

_SENTENCE = re.compile(r"(?<=[.!?…;:])\s+")
_CLAUSE = re.compile(r"(?<=[,–—])\s+")


def split_text(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Split text into chunks of at most ``limit`` characters, preferring sentence, then clause, then word breaks."""
    chunks: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n", text):
        paragraph = " ".join(paragraph.split())
        for sentence in _SENTENCE.split(paragraph):
            if not sentence:
                continue
            pieces = [sentence] if len(sentence) <= limit else _CLAUSE.split(sentence)
            current = ""
            for piece in pieces:
                for word in [piece] if len(piece) <= limit else piece.split(" "):
                    if current and len(current) + 1 + len(word) > limit:
                        chunks.append(current)
                        current = word
                    else:
                        current = f"{current} {word}" if current else word
            if current:
                chunks.append(current)
    return chunks


class Engine(Protocol):
    revision: str

    def synthesize(self, text: str, voice: Voice, speed: float) -> np.ndarray:
        """Return mono float32 samples at ``audio.SAMPLE_RATE``."""
        ...

    def loaded(self) -> list[str]: ...

    def preload(self, languages: list[str]) -> None: ...


class FakeEngine:
    """Deterministic tone instead of speech; one 0.1 s beep per word."""

    revision = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def synthesize(self, text: str, voice: Voice, speed: float) -> np.ndarray:
        self.calls.append((text, voice.id, speed))
        n = int(SAMPLE_RATE * 0.1 / speed) * max(1, len(text.split()))
        t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
        return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    def loaded(self) -> list[str]:
        return ["fake"]

    def preload(self, languages: list[str]) -> None:
        pass


class KokoroEngine:
    """Kokoro-82M for en/fr/it and the Thorsten-Voice fine-tune for de, loaded lazily on first use."""

    def __init__(self, device: str = "auto", thorsten_epoch: int = 5) -> None:
        self.device = device
        self.thorsten_epoch = thorsten_epoch
        self.revision = f"kokoro-82m+thorsten-ep{thorsten_epoch}"
        self._models: dict[ModelName, Any] = {}
        self._pipelines: dict[str, Any] = {}
        self._thorsten_voice: str | None = None
        self._init_lock = threading.Lock()
        # CPU inference already uses all cores; serialize per model so requests queue instead of thrashing.
        self._model_locks: dict[ModelName, threading.Lock] = {"base": threading.Lock(), "thorsten": threading.Lock()}

    def _device(self) -> str:
        if self.device != "auto":
            return self.device
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"

    def _model(self, name: ModelName) -> Any:
        if name in self._models:
            return self._models[name]
        from huggingface_hub import hf_hub_download
        from kokoro import KModel

        log.info("loading model %s", name)
        if name == "base":
            model = KModel(repo_id=BASE_REPO)
        else:
            suffix = "" if self.thorsten_epoch == 5 else f"_ep{self.thorsten_epoch}"
            config = hf_hub_download(THORSTEN_REPO, "config.json")
            weights = hf_hub_download(THORSTEN_REPO, f"model{suffix}.pth")
            self._thorsten_voice = hf_hub_download(THORSTEN_REPO, f"voices/thorsten{suffix}.pt")
            model = KModel(repo_id=BASE_REPO, config=config, model=weights)
        self._models[name] = model.to(self._device()).eval()
        return self._models[name]

    def _pipeline(self, voice: Voice) -> Any:
        with self._init_lock:
            if voice.lang_code in self._pipelines:
                return self._pipelines[voice.lang_code]
            from kokoro import KPipeline

            pipeline = KPipeline(lang_code=voice.lang_code, repo_id=BASE_REPO, model=self._model(voice.model))
            if voice.lang_code == "d":
                # Kokoro's vocabulary lacks the short ü 'ʏ'; 'y' is the closest it knows (see the model card).
                g2p = pipeline.g2p

                def patched(text: str) -> tuple[str, Any]:
                    ps, tokens = g2p(text)
                    return ps.replace("ʏ", "y"), tokens

                pipeline.g2p = patched
            self._pipelines[voice.lang_code] = pipeline
            return pipeline

    def synthesize(self, text: str, voice: Voice, speed: float) -> np.ndarray:
        pipeline = self._pipeline(voice)
        pack = self._thorsten_voice if voice.model == "thorsten" else voice.id
        chunks: list[np.ndarray] = []
        with self._model_locks[voice.model]:
            for result in pipeline("\n".join(split_text(text)), voice=pack, speed=speed):
                if result.audio is not None:
                    chunks.append(result.audio.detach().cpu().numpy())
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32)

    def loaded(self) -> list[str]:
        return sorted(self._models)

    def preload(self, languages: list[str]) -> None:
        for language in languages:
            if language not in LANGUAGES:
                raise ValueError(f"unknown language {language!r}")
            for voice in voices_for(language):
                self._pipeline(voice).load_voice(self._thorsten_voice if voice.model == "thorsten" else voice.id)
