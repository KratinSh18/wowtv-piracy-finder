"""
Shazam-style landmark (constellation) audio fingerprinting.

Why audio is the primary signal for catching stolen micro-dramas:
a pirate can crop the video, slap their own logo on it, change the resolution
or re-encode it -- but they almost always REUSE THE ORIGINAL AUDIO TRACK
(dialogue + background score). Audio landmarks survive MP3/AAC re-encoding,
volume changes and moderate noise, so an audio match is hard to dodge.

Algorithm (Wang, 2003):
  1. STFT spectrogram of mono audio.
  2. Pick spectral peaks (local maxima) -> a sparse "constellation" of points.
  3. Pair each anchor peak with a few peaks in a forward "target zone".
     Each pair -> a compact hash (f1, f2, dt) plus the anchor's time offset.
  4. Matching: a true hit produces MANY hashes that line up at a single
     consistent time offset (ref_time - query_time). We histogram those
     offsets; the tallest bin's height is the match score.

This module is pure numpy/scipy -- no ffmpeg needed -- so it can be unit tested
on raw sample arrays (see selftest.py).
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy import ndimage, signal

from .. import config


def frames_to_seconds(frames: float) -> float:
    return float(frames) * config.HOP / config.SAMPLE_RATE


def _spectrogram(samples: np.ndarray, sr: int) -> np.ndarray:
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    if sr != config.SAMPLE_RATE:
        samples = signal.resample_poly(samples, config.SAMPLE_RATE, sr)
    f, t, Z = signal.stft(
        samples,
        fs=config.SAMPLE_RATE,
        window=config.WINDOW,
        nperseg=config.N_FFT,
        noverlap=config.N_FFT - config.HOP,
        boundary=None,
        padded=False,
    )
    mag = np.abs(Z)
    return 20.0 * np.log10(mag + 1e-6)  # dB scale -> log-magnitude spectrogram


def _peaks(spec: np.ndarray):
    """Return constellation points sorted by (time_frame, freq_bin)."""
    footprint = (config.PEAK_NEIGH_F, config.PEAK_NEIGH_T)
    local_max = ndimage.maximum_filter(spec, size=footprint, mode="constant", cval=-200.0)
    threshold = np.percentile(spec, config.PEAK_PERCENTILE)
    mask = (spec == local_max) & (spec > threshold)
    fbins, tframes = np.where(mask)
    pts = sorted(zip(tframes.tolist(), fbins.tolist()))
    return pts


def _hashes(peaks):
    """Combinatorial hashing of the constellation -> [(hash_int, anchor_time), ...]."""
    out = []
    n = len(peaks)
    for i in range(n):
        t1, f1 = peaks[i]
        paired = 0
        for j in range(i + 1, n):
            t2, f2 = peaks[j]
            dt = t2 - t1
            if dt < config.MIN_DT:
                continue
            if dt > config.TARGET_T:
                break  # peaks are time-sorted: no further j can be in the zone
            if abs(f2 - f1) > config.TARGET_F:
                continue
            h = ((f1 & 0x3FF) << 20) | ((f2 & 0x3FF) << 10) | (dt & 0x3FF)
            out.append((h, t1))
            paired += 1
            if paired >= config.FAN_OUT:
                break
    return out


def fingerprint_samples(samples: np.ndarray, sr: int = config.SAMPLE_RATE):
    """Fingerprint a raw audio array. Returns [(hash_int, anchor_time_frame), ...]."""
    spec = _spectrogram(np.asarray(samples, dtype=np.float32), sr)
    return _hashes(_peaks(spec))


def fingerprint_file(path):
    """Fingerprint an audio/video file via ffmpeg decode."""
    from .. import media
    samples, sr = media.decode_audio(path)
    return fingerprint_samples(samples, sr)


def resample_by(samples: np.ndarray, factor: float) -> np.ndarray:
    """Time-stretch samples by `factor` (output length ~= len*factor).

    Used to undo a pirate's linear speed change: if they played the clip at
    1.05x (shorter), resampling the suspect by 1.05 restores the original
    timeline so the landmark offsets line up again.
    """
    from fractions import Fraction
    if abs(factor - 1.0) < 1e-6:
        return samples
    frac = Fraction(float(factor)).limit_denominator(200)
    return signal.resample_poly(samples, frac.numerator, frac.denominator)


def align(query_hashes, ref_hashes):
    """Standalone aligner (used in selftest). Returns (votes, offset_frames).

    The production path uses the SQLite index (matcher.audio_match); this is the
    in-memory equivalent for verifying the algorithm without a database.
    """
    ref = defaultdict(list)
    for h, t in ref_hashes:
        ref[h].append(t)
    offsets = defaultdict(int)
    for h, tq in query_hashes:
        for tr in ref.get(h, ()):  # noqa: SIM118
            offsets[tr - tq] += 1
    if not offsets:
        return 0, 0
    best_offset = max(offsets, key=offsets.get)
    return offsets[best_offset], best_offset
