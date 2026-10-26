"""Resampling and encoding of the 24 kHz float output into the formats PBXs use."""

import io
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import soxr

SAMPLE_RATE = 24000


@dataclass(frozen=True)
class AudioFormat:
    name: str
    rate: int
    container: str  # "wav", "raw16", "ulaw" or "alaw"
    ext: str
    content_type: str
    description: str


FORMATS: dict[str, AudioFormat] = {
    f.name: f
    for f in (
        AudioFormat("wav", 24000, "wav", "wav", "audio/wav", "WAV, 24 kHz, 16 bit (original quality)"),
        AudioFormat("wav16", 16000, "wav", "wav", "audio/wav", "WAV, 16 kHz, 16 bit (wideband)"),
        AudioFormat("wav8", 8000, "wav", "wav", "audio/wav", "WAV, 8 kHz, 16 bit (telephony)"),
        AudioFormat("sln", 8000, "raw16", "sln", "audio/L16;rate=8000", "Asterisk .sln, raw 8 kHz 16 bit"),
        AudioFormat("sln16", 16000, "raw16", "sln16", "audio/L16;rate=16000", "Asterisk .sln16, raw 16 kHz 16 bit"),
        AudioFormat("ulaw", 8000, "ulaw", "ulaw", "audio/basic", "G.711 µ-law, raw 8 kHz"),
        AudioFormat("alaw", 8000, "alaw", "alaw", "audio/x-alaw-basic", "G.711 A-law, raw 8 kHz"),
    )
}


def resample(samples: np.ndarray, rate: int) -> np.ndarray:
    if rate == SAMPLE_RATE:
        return samples
    return soxr.resample(samples, SAMPLE_RATE, rate, quality="HQ")


def to_pcm16(samples: np.ndarray) -> np.ndarray:
    return (np.clip(samples, -1.0, 1.0) * 32767.0).round().astype("<i2")


def linear_to_ulaw(pcm: np.ndarray) -> np.ndarray:
    """G.711 µ-law, same output as the classic Sun ``linear2ulaw``."""
    x = pcm.astype(np.int32) >> 2  # µ-law works on 14 bit
    mask = np.where(x < 0, 0x7F, 0xFF)
    mag = np.minimum(np.abs(x), 8159) + 0x21
    exponent = np.floor(np.log2(mag)).astype(np.int32) - 5
    mantissa = (mag >> (exponent + 1)) & 0x0F
    code = np.where(exponent > 7, 0x7F, (exponent << 4) | mantissa)
    return (code ^ mask).astype(np.uint8)


def linear_to_alaw(pcm: np.ndarray) -> np.ndarray:
    """G.711 A-law, same output as the classic Sun ``linear2alaw``."""
    x = pcm.astype(np.int32) >> 3  # A-law works on 13 bit
    sign = np.where(x >= 0, 0xD5, 0x55)
    mag = np.where(x >= 0, x, -x - 1)
    mag = np.minimum(mag, 0xFFF)
    exponent = np.where(mag < 32, 0, np.floor(np.log2(np.maximum(mag, 1))).astype(np.int32) - 4)
    mantissa = np.where(exponent == 0, mag >> 1, mag >> exponent) & 0x0F
    return ((((exponent << 4) | mantissa) ^ sign) & 0xFF).astype(np.uint8)


def encode(samples: np.ndarray, fmt: AudioFormat) -> bytes:
    pcm = to_pcm16(resample(samples, fmt.rate))
    if fmt.container == "wav":
        buf = io.BytesIO()
        sf.write(buf, pcm, fmt.rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()
    if fmt.container == "raw16":
        return pcm.tobytes()
    if fmt.container == "ulaw":
        return linear_to_ulaw(pcm).tobytes()
    if fmt.container == "alaw":
        return linear_to_alaw(pcm).tobytes()
    raise ValueError(f"unknown container {fmt.container!r}")
