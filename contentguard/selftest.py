"""
End-to-end self test -- proves the engine actually works WITHOUT needing any
real content or even ffmpeg. It synthesises signals, applies the same kinds of
mangling a pirate would (re-encode/noise/zoom/logo/crop), and checks that the
fingerprints still match and the watermark still survives.

Run:  python -m contentguard selftest
"""
from __future__ import annotations

import io

import numpy as np
from scipy.signal import butter, lfilter

from . import config, matcher, watermark
from .db import FingerprintDB
from .fingerprint import audio as audio_fp
from .fingerprint import video as video_fp

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"


def _synth_audio(dur=30.0, seed=0):
    """A spectrally RICH signal (many simultaneous drifting partials + noise),
    so the constellation density resembles real dialogue+music rather than a
    bare tone."""
    sr = config.SAMPLE_RATE
    t = np.arange(int(sr * dur)) / sr
    rng = np.random.default_rng(seed)
    sig = np.zeros_like(t)
    base_freqs = [180, 240, 320, 415, 540, 700, 910, 1180, 1500, 1950, 2500, 3200]
    for k, f0 in enumerate(base_freqs):
        drift = 1.0 + 0.02 * np.sin(2 * np.pi * (0.05 + 0.01 * k) * t + k)
        amp = 0.5 * (0.6 + 0.4 * np.sin(2 * np.pi * (0.1 + 0.03 * k) * t))
        sig += amp * np.sin(2 * np.pi * f0 * drift * t)
    sig += 0.05 * rng.standard_normal(t.shape)
    return sig / np.max(np.abs(sig))


def test_audio():
    sr = config.SAMPLE_RATE
    original = _synth_audio()
    db = FingerprintDB(":memory:")
    wid = db.add_work("WOW Drama #1", "/masters/drama1.mp4", 30.0)
    db.add_audio_hashes(wid, audio_fp.fingerprint_samples(original, sr))

    # --- pirate it: take 12s, mp3-style lowpass, add noise, drop gain ---
    rng = np.random.default_rng(7)
    start, length = 10.0, 12.0
    seg = original[int(start * sr):int((start + length) * sr)].copy()
    b, a = butter(6, 3500 / (sr / 2), btype="low")
    seg = lfilter(b, a, seg)
    seg = seg * 0.8 + 0.05 * rng.standard_normal(seg.shape)

    res = matcher.audio_match(audio_fp.fingerprint_samples(seg, sr), db, top=3)
    top = res[0] if res else {"work_id": -1, "votes": 0, "offset_sec": -99}
    ok = (top["work_id"] == wid
          and top["votes"] >= config.MIN_AUDIO_MATCH
          and abs(top["offset_sec"] - start) < 1.5)
    print(f"  [{PASS if ok else FAIL}] audio: matched work={top['work_id']} "
          f"votes={top['votes']} offset={top['offset_sec']}s (expected ~{start}s)")
    return ok


def _synth_frames(n=24, h=160, w=288, seed=0):
    """Frames with strong, distinct STRUCTURE (shapes/edges), like real video.
    pHash is stable on structured frames and unstable on smooth gradients, so
    this is both more realistic and a fair test."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    bg = (60 + 40 * np.sin(xx / 40.0)).astype(np.float32)
    frames = []
    for i in range(n):
        img = bg.copy()
        rx = int(20 + (w - 130) * (0.5 + 0.5 * np.sin(2 * np.pi * i / n)))  # drifting bar
        img[40:115, rx:rx + 95] = 220
        cy, cx = 115, int(45 + (w - 90) * (i / n))                          # moving disc
        img[(yy - cy) ** 2 + (xx - cx) ** 2 < 24 ** 2] = 20
        img[18:30, :] = 180                                                 # top banner
        img += 4 * rng.standard_normal((h, w))
        frames.append(np.clip(img, 0, 255).astype(np.uint8))
    return frames


def _pirate_frame(g):
    """Apply realistic pirate edits: 10% zoom-crop, small corner logo, slight
    contrast shift and noise."""
    from PIL import Image
    img = Image.fromarray(g)
    W, H = img.size
    cw, ch = int(W * 0.90), int(H * 0.90)        # 10% zoom
    left, top = (W - cw) // 2, (H - ch) // 2
    img = img.crop((left, top, left + cw, top + ch)).resize((W, H), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32)
    arr[int(H * 0.04):int(H * 0.14), int(W * 0.84):int(W * 0.98)] = 255  # small corner logo
    arr = arr * 0.95 + 5                                                 # contrast/brightness shift
    arr += 5 * np.random.default_rng(3).standard_normal(arr.shape)
    return np.clip(arr, 0, 255).astype(np.uint8)


def test_video():
    frames = _synth_frames()
    db = FingerprintDB(":memory:")
    wid = db.add_work("WOW Drama #1 (video)", "/masters/drama1.mp4", 24.0)
    # Store BOTH orientations on the reference, exactly like flip-invariant ingest.
    ref = []
    for i, g in enumerate(frames):
        ref.append((i, video_fp.phash_array(g)))
        ref.append((i, video_fp.phash_array(g[:, ::-1])))
    db.add_video_hashes(wid, ref)

    q_normal = [(i, video_fp.phash_array(_pirate_frame(g))) for i, g in enumerate(frames)]
    q_flip = [(i, video_fp.phash_array(_pirate_frame(g[:, ::-1]))) for i, g in enumerate(frames)]
    ov_n, m_n = matcher.video_match(q_normal, db, wid)
    ov_f, m_f = matcher.video_match(q_flip, db, wid)
    ok = ov_n >= config.VIDEO_MATCH_FRAC and ov_f >= config.VIDEO_MATCH_FRAC
    print(f"  [{PASS if ok else FAIL}] video: normal {m_n}/{len(q_normal)} ({ov_n*100:.0f}%), "
          f"MIRRORED {m_f}/{len(q_flip)} ({ov_f*100:.0f}%) matched after zoom+logo+noise "
          f"(need >= {config.VIDEO_MATCH_FRAC*100:.0f}%)")
    return ok


def test_audio_speed():
    """A pirate who speeds the clip to 1.05x defeats exact-offset voting; the
    multi-speed search must recover it."""
    sr = config.SAMPLE_RATE
    original = _synth_audio()
    db = FingerprintDB(":memory:")
    wid = db.add_work("WOW Drama #2", "/masters/drama2.mp4", 30.0)
    db.add_audio_hashes(wid, audio_fp.fingerprint_samples(original, sr))

    start, length = 8.0, 12.0
    seg = original[int(start * sr):int((start + length) * sr)].copy()
    sped = audio_fp.resample_by(seg, 1.0 / 1.05)   # 1.05x faster playback

    base = matcher.audio_match(audio_fp.fingerprint_samples(sped, sr), db, top=1)
    base_votes = base[0]["votes"] if base else 0

    best = {"score": 0, "speed": 1.0}
    for r in config.SPEED_GRID:
        c = matcher.audio_match(
            audio_fp.fingerprint_samples(audio_fp.resample_by(sped, r), sr), db, top=1)
        s = c[0]["votes"] if c else 0
        if s > best["score"]:
            best = {"score": s, "speed": r}

    ok = best["score"] >= config.MIN_AUDIO_MATCH and best["score"] > base_votes
    print(f"  [{PASS if ok else FAIL}] audio speed: 1.05x rip gave {base_votes} votes "
          f"uncorrected -> {best['score']} votes after speed search "
          f"(recovered at {best['speed']}x)")
    return ok


def test_watermark():
    from PIL import Image
    yy, xx = np.mgrid[0:256, 0:256]
    base = np.clip(128 + 60 * np.sin(xx / 10.0) + 50 * np.cos(yy / 13.0), 0, 255)
    rgb = np.stack([base, np.roll(base, 30, 0), np.roll(base, 60, 1)], -1).astype(np.uint8)

    pid = 0x0BADF00D
    wm = watermark.embed_image(rgb, pid)
    psnr = 10 * np.log10(255.0 ** 2 / np.mean((rgb.astype(float) - wm) ** 2))

    buf = io.BytesIO()
    Image.fromarray(wm).save(buf, "JPEG", quality=80)   # simulate re-encode
    buf.seek(0)
    rgb2 = np.asarray(Image.open(buf).convert("RGB"))
    res = watermark.extract_image(rgb2)
    ok = res["present"] and res["id"] == pid
    print(f"  [{PASS if ok else FAIL}] watermark: recovered id=0x{res['id']:08X} "
          f"(embedded 0x{pid:08X}) conf={res['confidence']} after JPEG q80 | "
          f"invisibility PSNR={psnr:.1f}dB")
    return ok


def run() -> int:
    print("ContentGuard self test (synthetic data, no ffmpeg needed)\n")
    results = []
    for name, fn in [("AUDIO fingerprint", test_audio),
                     ("AUDIO speed-search", test_audio_speed),
                     ("VIDEO fingerprint (+mirror)", test_video),
                     ("WATERMARK", test_watermark)]:
        try:
            results.append(fn())
        except Exception as e:  # noqa: BLE001
            print(f"  [{FAIL}] {name} raised: {e}")
            results.append(False)
    print()
    if all(results):
        print(f"{PASS}: all {len(results)} subsystems working.")
        return 0
    print(f"{FAIL}: {sum(not r for r in results)}/{len(results)} subsystem(s) failed.")
    return 1
