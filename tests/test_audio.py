import io
import warnings

import numpy as np
import pytest
import soundfile as sf

from restfultts.audio import FORMATS, SAMPLE_RATE, encode, linear_to_alaw, linear_to_ulaw

ALL_PCM = np.arange(-32768, 32768, dtype="<i2")


def _audioop():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return pytest.importorskip("audioop")


def test_ulaw_matches_audioop_for_every_sample():
    expected = np.frombuffer(_audioop().lin2ulaw(ALL_PCM.tobytes(), 2), np.uint8)
    assert np.array_equal(linear_to_ulaw(ALL_PCM), expected)


def test_alaw_matches_audioop_for_every_sample():
    expected = np.frombuffer(_audioop().lin2alaw(ALL_PCM.tobytes(), 2), np.uint8)
    assert np.array_equal(linear_to_alaw(ALL_PCM), expected)


@pytest.mark.parametrize("name", ["wav", "wav16", "wav8"])
def test_wav_formats_have_their_rate(name):
    one_second = np.zeros(SAMPLE_RATE, dtype=np.float32)
    data, rate = sf.read(io.BytesIO(encode(one_second, FORMATS[name])), dtype="int16")
    assert rate == FORMATS[name].rate
    assert len(data) == rate


RAW_SIZES = [("sln", 16000), ("sln16", 32000), ("ulaw", 8000), ("alaw", 8000)]


@pytest.mark.parametrize(("name", "bytes_per_second"), RAW_SIZES)
def test_raw_formats_have_their_size(name, bytes_per_second):
    one_second = np.zeros(SAMPLE_RATE, dtype=np.float32)
    assert len(encode(one_second, FORMATS[name])) == bytes_per_second


def test_clipping():
    data = encode(np.array([2.0, -2.0], dtype=np.float32), FORMATS["sln16"])
    assert data  # resampled, but must not wrap around
    assert np.abs(np.frombuffer(data, "<i2")).max() <= 32767
