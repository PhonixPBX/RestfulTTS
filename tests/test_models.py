"""Real synthesis with the Kokoro models; run with ``pytest -m models`` (downloads ~700 MB on first run)."""

import pytest

from restfultts.audio import SAMPLE_RATE
from restfultts.engine import KokoroEngine
from restfultts.voices import resolve

pytestmark = pytest.mark.models

TEXTS = {
    "de": "Guten Tag. Für den Verkauf drücken Sie die Eins.",
    "en": "Hello. For sales, press one.",
    "fr": "Bonjour. Pour les ventes, appuyez sur un.",
    "it": "Buongiorno. Per le vendite, premere uno.",
}


@pytest.fixture(scope="module")
def engine():
    return KokoroEngine(device="cpu")


@pytest.mark.parametrize("language", TEXTS)
def test_synthesize(engine, language):
    samples = engine.synthesize(TEXTS[language], resolve(language=language), 1.0)
    seconds = len(samples) / SAMPLE_RATE
    assert 1.0 < seconds < 10.0
    assert abs(samples).max() > 0.05
