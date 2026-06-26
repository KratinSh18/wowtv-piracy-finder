"""
Invisible forensic watermarking (the PROACTIVE layer).

Passive fingerprinting (audio/video) catches re-uploads *after* the fact. A
watermark you embed into your masters BEFORE release lets you (a) prove the clip
on a rival app is unmistakably yours, and (b) -- if you embed a per-partner id --
trace WHICH distribution leaked.

Scheme: blind block-DCT watermark (Koch-Zhao). For every 8x8 block of the luma
(Y) channel we encode one bit by enforcing an inequality between two mid-band DCT
coefficients. The payload (a 16-bit sync word + a 32-bit id) is repeated across
all blocks and recovered by majority vote -> robust to JPEG/H.264 re-encoding,
resizing and mild cropping. The change is below the visual threshold.

Pure numpy + Pillow for the image path (unit-tested in selftest). The video path
uses ffmpeg raw-frame pipes and is marked experimental.
"""
from __future__ import annotations

import numpy as np
from scipy.fftpack import dct, idct

SYNC = 0xACE1            # 16-bit sync word -> tells us a watermark is present
ID_BITS = 32
MSG_BITS = 16 + ID_BITS  # 48 bits total
C1 = (3, 1)              # mid-band DCT coefficient positions (the bit carriers)
C2 = (1, 3)
STRENGTH = 14.0          # embedding strength: higher = more robust, more visible


def _dct2(b):
    return dct(dct(b, axis=0, norm="ortho"), axis=1, norm="ortho")


def _idct2(b):
    return idct(idct(b, axis=0, norm="ortho"), axis=1, norm="ortho")


def _payload_bits(payload_id: int):
    val = (SYNC << ID_BITS) | (int(payload_id) & ((1 << ID_BITS) - 1))
    return [(val >> (MSG_BITS - 1 - i)) & 1 for i in range(MSG_BITS)]


def embed_image(rgb: np.ndarray, payload_id: int, strength: float = STRENGTH) -> np.ndarray:
    from PIL import Image
    ycc = np.asarray(Image.fromarray(rgb).convert("YCbCr"), dtype=np.float32).copy()
    Y = ycc[:, :, 0]
    bits = _payload_bits(payload_id)
    bh, bw = Y.shape[0] // 8, Y.shape[1] // 8
    idx = 0
    for by in range(bh):
        for bx in range(bw):
            bit = bits[idx % MSG_BITS]
            idx += 1
            ys, xs = by * 8, bx * 8
            d = _dct2(Y[ys:ys + 8, xs:xs + 8])
            a, b = d[C1], d[C2]
            mid = (a + b) / 2.0
            if bit == 1 and a < b + strength:
                a, b = mid + strength / 2, mid - strength / 2
            elif bit == 0 and b < a + strength:
                a, b = mid - strength / 2, mid + strength / 2
            d[C1], d[C2] = a, b
            Y[ys:ys + 8, xs:xs + 8] = _idct2(d)
    ycc[:, :, 0] = np.clip(Y, 0, 255)
    return np.asarray(Image.fromarray(ycc.astype(np.uint8), "YCbCr").convert("RGB"))


def _vote_image(rgb: np.ndarray):
    """Per-bit [zeros, ones] vote tallies from one image."""
    from PIL import Image
    Y = np.asarray(Image.fromarray(rgb).convert("YCbCr"), dtype=np.float32)[:, :, 0]
    bh, bw = Y.shape[0] // 8, Y.shape[1] // 8
    votes = [[0, 0] for _ in range(MSG_BITS)]
    idx = 0
    for by in range(bh):
        for bx in range(bw):
            d = _dct2(Y[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8])
            bit = 1 if d[C1] > d[C2] else 0
            votes[idx % MSG_BITS][bit] += 1
            idx += 1
    return votes


def _decode(votes):
    bits = [1 if v[1] >= v[0] else 0 for v in votes]
    agree = np.mean([max(v) / max(1, sum(v)) for v in votes])
    val = 0
    for b in bits:
        val = (val << 1) | b
    sync = val >> ID_BITS
    return {
        "present": sync == SYNC,
        "id": val & ((1 << ID_BITS) - 1),
        "confidence": round(float(agree), 3),
    }


def extract_image(rgb: np.ndarray):
    return _decode(_vote_image(rgb))


# ---- file helpers ---------------------------------------------------------
def embed_image_file(in_path: str, out_path: str, payload_id: int,
                     strength: float = STRENGTH):
    from PIL import Image
    rgb = np.asarray(Image.open(in_path).convert("RGB"))
    Image.fromarray(embed_image(rgb, payload_id, strength)).save(out_path)
    return out_path


def extract_image_file(in_path: str):
    from PIL import Image
    return extract_image(np.asarray(Image.open(in_path).convert("RGB")))


# ---- video (experimental, needs ffmpeg) -----------------------------------
def _video_dims(path):
    import json
    import subprocess
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path]
    s = json.loads(subprocess.run(cmd, stdout=subprocess.PIPE).stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 25.0
    return int(s["width"]), int(s["height"]), fps


def embed_video(in_path: str, out_path: str, payload_id: int,
                strength: float = STRENGTH):
    """Watermark every frame, re-mux original audio. Experimental + slow."""
    import subprocess
    from . import media
    media._require_ffmpeg()
    w, h, fps = _video_dims(in_path)
    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", in_path, "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
         "-i", in_path, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         "-c:a", "copy", "-shortest", out_path], stdin=subprocess.PIPE)
    fsize = w * h * 3
    try:
        while True:
            raw = dec.stdout.read(fsize)
            if len(raw) < fsize:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
            enc.stdin.write(embed_image(frame, payload_id, strength).tobytes())
    finally:
        enc.stdin.close()
        dec.wait()
        enc.wait()
    return out_path


def extract_video(in_path: str, sample_frames: int = 30):
    """Aggregate votes across sampled frames -> robust recovery."""
    from PIL import Image
    from . import media
    frames = media.extract_frames(in_path, fps=1.0)[:sample_frames]
    if not frames:
        raise RuntimeError("no frames extracted")
    # extract_frames returns grayscale; re-read as RGB for the Y channel.
    import os
    import shutil
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="cg_wmx_")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-i", in_path, "-vf", "fps=1",
                        "-frames:v", str(sample_frames), os.path.join(d, "f_%04d.png")],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        total = [[0, 0] for _ in range(MSG_BITS)]
        for fn in sorted(os.listdir(d)):
            rgb = np.asarray(Image.open(os.path.join(d, fn)).convert("RGB"))
            for i, v in enumerate(_vote_image(rgb)):
                total[i][0] += v[0]
                total[i][1] += v[1]
        return _decode(total)
    finally:
        shutil.rmtree(d, ignore_errors=True)
