"""
Media I/O helpers. Everything that touches ffmpeg/ffprobe lives here so the rest
of the pipeline stays pure-numpy and unit-testable without external binaries.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

import numpy as np

from . import config


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _require_ffmpeg():
    if not have_ffmpeg():
        raise RuntimeError(
            "ffmpeg/ffprobe not found on PATH. Install it (https://ffmpeg.org/download.html) "
            "or use the pure-numpy `selftest` to verify the engine."
        )


def decode_audio(path, sr: int = config.SAMPLE_RATE):
    """Decode any media file to mono float32 PCM at the target sample rate."""
    _require_ffmpeg()
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio decode failed for {path}:\n"
                           f"{proc.stderr.decode(errors='ignore')[:600]}")
    samples = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        raise RuntimeError(f"No audio decoded from {path} (silent or no audio stream?)")
    return samples, sr


def probe_duration(path) -> float:
    if not have_ffmpeg():
        return 0.0
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "json", str(path)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def extract_frames(path, fps: float = config.VIDEO_FPS):
    """Sample frames at `fps` and return [(t_seconds, gray_uint8_ndarray), ...]."""
    _require_ffmpeg()
    from PIL import Image

    d = tempfile.mkdtemp(prefix="cg_frames_")
    try:
        out = os.path.join(d, "f_%06d.png")
        cmd = ["ffmpeg", "-v", "error", "-i", str(path),
               "-vf", f"fps={fps}", "-vsync", "vfr", out]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg frame extract failed for {path}:\n"
                               f"{proc.stderr.decode(errors='ignore')[:600]}")
        frames = []
        for i, fn in enumerate(sorted(os.listdir(d))):
            img = Image.open(os.path.join(d, fn)).convert("L")
            frames.append((i / float(fps), np.asarray(img, dtype=np.uint8)))
        return frames
    finally:
        shutil.rmtree(d, ignore_errors=True)


def is_url(s: str) -> bool:
    return str(s).startswith(("http://", "https://"))


def platform_of(source: str) -> str:
    """Human-readable platform/source label for any suspect, from its URL host
    (works for ANY site yt-dlp supports), or 'local-file' for a path."""
    if is_url(source):
        host = urlparse(str(source)).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    return "local-file"


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    """SHA-256 of the exact bytes analysed -- chain-of-custody for takedowns."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def list_titles(url: str):
    """List the titles in a rival channel / playlist / profile via yt-dlp,
    without downloading any video (flat playlist). Public pages only."""
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp not found. `pip install yt-dlp` to list titles.")
    cmd = ["yt-dlp", "--flat-playlist", "--ignore-errors",
           "--print", "%(title)s", str(url)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    titles = [ln.strip() for ln in proc.stdout.decode(errors="ignore").splitlines()
              if ln.strip()]
    if not titles:
        raise RuntimeError(f"yt-dlp returned no titles for {url}:\n"
                           f"{proc.stderr.decode(errors='ignore')[:400]}")
    return titles


def download(url: str, dest_dir: str | None = None) -> str:
    """Download a suspect clip from a URL using yt-dlp (must be installed).

    Used by `contentguard scan <url>` to fetch a clip from a rival platform's
    public share page for evidence. Respect each platform's Terms of Service and
    your local laws before crawling at scale -- see README "Legal & enforcement".
    """
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp not found. `pip install yt-dlp` to fetch URLs.")
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="cg_dl_")
    out = os.path.join(dest_dir, "suspect.%(ext)s")
    cmd = ["yt-dlp", "-q", "-o", out, "-f", "mp4/best", str(url)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed:\n{proc.stderr.decode(errors='ignore')[:600]}")
    files = [os.path.join(dest_dir, f) for f in os.listdir(dest_dir)]
    if not files:
        raise RuntimeError("yt-dlp produced no file.")
    return max(files, key=os.path.getsize)
