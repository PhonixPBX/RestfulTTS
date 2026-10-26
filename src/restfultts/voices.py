"""The voices this service offers, per language."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

ModelName = Literal["base", "thorsten"]


@dataclass(frozen=True)
class Voice:
    id: str
    language: str
    lang_code: str  # KPipeline lang_code
    model: ModelName
    gender: Literal["female", "male"]
    label: str
    quality: str  # overall grade from Kokoro's VOICES.md, "-" if not graded

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


VOICES: tuple[Voice, ...] = (
    Voice("thorsten", "de", "d", "thorsten", "male", "Thorsten (neutral)", "-"),
    Voice("af_heart", "en", "a", "base", "female", "Heart (US)", "A"),
    Voice("af_bella", "en", "a", "base", "female", "Bella (US)", "A-"),
    Voice("am_michael", "en", "a", "base", "male", "Michael (US)", "C+"),
    Voice("bf_emma", "en", "b", "base", "female", "Emma (UK)", "B-"),
    Voice("bm_george", "en", "b", "base", "male", "George (UK)", "C"),
    Voice("ff_siwis", "fr", "f", "base", "female", "Siwis", "B-"),
    Voice("if_sara", "it", "i", "base", "female", "Sara", "C"),
    Voice("im_nicola", "it", "i", "base", "male", "Nicola", "C"),
)

LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English", "fr": "Français", "it": "Italiano"}
DEFAULT_VOICE: dict[str, str] = {"de": "thorsten", "en": "af_heart", "fr": "ff_siwis", "it": "if_sara"}

_BY_ID = {v.id: v for v in VOICES}


class VoiceError(ValueError):
    pass


def voices_for(language: str | None = None) -> list[Voice]:
    return [v for v in VOICES if language is None or v.language == language]


def resolve(voice: str | None = None, language: str | None = None) -> Voice:
    """Pick a voice by id, or the default voice of a language; ``voice`` wins when both are given."""
    if voice:
        try:
            found = _BY_ID[voice]
        except KeyError:
            raise VoiceError(f"unknown voice {voice!r}") from None
        if language and found.language != language:
            raise VoiceError(f"voice {voice!r} does not speak {language!r}")
        return found
    if language:
        try:
            return _BY_ID[DEFAULT_VOICE[language]]
        except KeyError:
            raise VoiceError(f"unknown language {language!r}, use one of {', '.join(LANGUAGES)}") from None
    raise VoiceError("either voice or language is required")
