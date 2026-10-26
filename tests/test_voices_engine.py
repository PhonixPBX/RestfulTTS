import pytest

from restfultts.engine import CHUNK_CHARS, split_text
from restfultts.voices import DEFAULT_VOICE, LANGUAGES, VOICES, VoiceError, resolve


def test_every_language_has_a_default_voice_of_that_language():
    for lang in LANGUAGES:
        assert resolve(language=lang).language == lang
    assert set(DEFAULT_VOICE) == set(LANGUAGES)
    assert {v.language for v in VOICES} == set(LANGUAGES)


def test_german_is_thorsten():
    voice = resolve(language="de")
    assert (voice.id, voice.model, voice.lang_code) == ("thorsten", "thorsten", "d")


def test_resolve_errors():
    with pytest.raises(VoiceError):
        resolve("nobody")
    with pytest.raises(VoiceError):
        resolve(language="xx")
    with pytest.raises(VoiceError):
        resolve("thorsten", "en")
    with pytest.raises(VoiceError):
        resolve()


def test_split_text_keeps_sentences_together():
    assert split_text("Hallo Welt. Wie geht's?\n\nGut!") == ["Hallo Welt.", "Wie geht's?", "Gut!"]


def test_split_text_breaks_long_sentences():
    sentence = ", ".join(["eins zwei drei vier fünf sechs sieben acht"] * 20) + "."
    chunks = split_text(sentence)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert " ".join(chunks).split() == sentence.split()


def test_split_text_without_any_break():
    chunks = split_text("x" * 600)
    assert chunks == ["x" * 600]  # a single word cannot be split, Kokoro truncates it
