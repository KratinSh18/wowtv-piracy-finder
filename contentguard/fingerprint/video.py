"""
Perceptual video fingerprinting.

We sample frames (default 1 fps) and compute a 64-bit DCT perceptual hash
(pHash) per frame. pHash captures the low-frequency structure of an image, so
it stays stable under re-encoding, resizing, mild colour shifts and light
overlays -- exactly the edits a pirate applies. We then ask: what fraction of a
suspect's frames match *some* frame of a candidate reference work within a small
Hamming distance?

Video is the SECONDARY signal. It confirms an audio hit and also catches the
case where someone muted/replaced the audio but kept the visuals.
"""
from __future__ import annotations

import numpy as np
from scipy.fftpack import dct

from .. import config

_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def phash_array(gray: np.ndarray) -> int:
    """64-bit DCT perceptual hash of a 2D grayscale image (uint8 or float)."""
    from PIL import Image

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    img = Image.fromarray(gray).resize(
        (config.PHASH_HIGHFREQ, config.PHASH_HIGHFREQ), Image.LANCZOS
    )
    a = np.asarray(img, dtype=np.float32)
    coeffs = dct(dct(a, axis=0, norm="ortho"), axis=1, norm="ortho")
    low = coeffs[: config.PHASH_SIZE, : config.PHASH_SIZE]
    # Threshold against the median of the AC coefficients only. The DC term
    # (low[0,0]) encodes overall brightness and dwarfs the rest; including it in
    # the median collapses most bits and destroys discrimination. Excluding it is
    # the standard pHash recipe and also makes the hash brightness-invariant.
    med = np.median(low.flatten()[1:])
    bits = (low > med).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    x = a ^ b
    d = 0
    while x:
        d += _POPCOUNT[x & 0xFF]
        x >>= 8
    return int(d)


def fingerprint_file(path, include_flip=False):
    """Return [(t_seconds, phash_int), ...] for a video file (via ffmpeg).

    With include_flip=True, also emit the hash of each horizontally-mirrored
    frame (same timestamp). Storing both orientations on the *reference* side
    means a pirate who flips the video is still caught, at the cost of doubling
    only the (sparse, 1 fps) video index. Mirror/flip is the single most common
    vertical-drama evasion, so reference ingest turns this on by default.
    """
    from .. import media
    out = []
    for t, g in media.extract_frames(path):
        out.append((t, phash_array(g)))
        if include_flip:
            out.append((t, phash_array(g[:, ::-1])))
    return out
