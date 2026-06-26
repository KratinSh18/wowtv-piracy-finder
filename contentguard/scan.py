"""
Scan a suspect clip (a file, a directory of clips, or a URL) against the
reference DB and report what -- if anything -- it matches.
"""
from __future__ import annotations

import os

from . import config, matcher, media
from .db import FingerprintDB
from .fingerprint import audio as audio_fp
from .fingerprint import video as video_fp

MEDIA_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv",
              ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus"}


def _best_speed_audio(samples, sr, db, top, speed_search):
    """Fingerprint the suspect at several resample ratios; keep the variant with
    the most aligned audio votes. Undoes linear speed-change evasion."""
    speeds = config.SPEED_GRID if speed_search else [1.0]
    best = {"score": -1, "speed": 1.0, "ah": []}
    for r in speeds:
        ah = audio_fp.fingerprint_samples(audio_fp.resample_by(samples, r), sr)
        cands = matcher.audio_match(ah, db, top=top)
        score = cands[0]["votes"] if cands else 0
        if score > best["score"]:
            best = {"score": score, "speed": r, "ah": ah}
    return best


def scan_file(db: FingerprintDB, path_or_url: str, do_video: bool = True,
              top: int = 5, source_url: str | None = None,
              speed_search: bool = True):
    cleanup = None
    path = path_or_url
    if media.is_url(path_or_url):
        source_url = source_url or path_or_url
        path = media.download(path_or_url)
        cleanup = os.path.dirname(path)

    try:
        source = source_url or path_or_url
        sha256 = media.sha256_file(path)
        samples, sr = media.decode_audio(path)
        best = _best_speed_audio(samples, sr, db, top, speed_search)
        ah = best["ah"]
        vph = video_fp.fingerprint_file(path) if do_video else []
        results = matcher.match(ah, vph, db, top=top)
        return {
            "suspect": source,
            "platform": media.platform_of(source),
            "sha256": sha256,
            "duration_sec": round(media.probe_duration(path), 1),
            "detected_speed": best["speed"],
            "query_audio_hashes": len(ah),
            "query_video_frames": len(vph),
            "candidates": results,
            "top_verdict": results[0]["verdict"] if results else "NO MATCH",
        }
    finally:
        if cleanup:
            import shutil
            shutil.rmtree(cleanup, ignore_errors=True)


def _iter_media(path: str):
    if os.path.isfile(path):
        yield path
        return
    for root, _dirs, files in os.walk(path):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in MEDIA_EXTS:
                yield os.path.join(root, f)


def _is_list_file(p: str) -> bool:
    return (not media.is_url(p) and os.path.isfile(p)
            and os.path.splitext(p)[1].lower() in {".txt", ".csv"})


def _read_list(p: str):
    """A watchlist of suspects (URLs and/or local paths), one per line, or a CSV
    with a url/source/link column (or first column). Lets you scan many clips
    from MANY different platforms in one run."""
    import csv
    if p.lower().endswith(".csv"):
        out = []
        with open(p, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            idx = 0
            if header:
                lh = [h.strip().lower() for h in header]
                for name in ("url", "source", "link"):
                    if name in lh:
                        idx = lh.index(name)
                        break
                else:
                    out.append(header[idx])  # first row was data, not a header
            for r in reader:
                if r and len(r) > idx and r[idx].strip():
                    out.append(r[idx].strip())
        return out
    with open(p, encoding="utf-8-sig") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]


def scan_one(db, suspect, do_video, top, speed_search):
    """Scan a single suspect; never raises -- returns an error record instead so
    a batch across many platforms keeps going if one URL/file fails."""
    try:
        return scan_file(db, suspect, do_video=do_video, top=top,
                         speed_search=speed_search)
    except Exception as e:  # noqa: BLE001
        return {
            "suspect": suspect,
            "platform": media.platform_of(suspect),
            "sha256": None, "duration_sec": 0.0, "detected_speed": 1.0,
            "query_audio_hashes": 0, "query_video_frames": 0,
            "candidates": [], "top_verdict": "ERROR", "error": str(e),
        }


def scan_path(db: FingerprintDB, target: str, do_video: bool = True,
              top: int = 5, speed_search: bool = True):
    if media.is_url(target):
        suspects = [target]
    elif _is_list_file(target):
        suspects = _read_list(target)
    elif os.path.isfile(target):
        suspects = [target]
    else:
        suspects = list(_iter_media(target))
    return [scan_one(db, s, do_video, top, speed_search) for s in suspects]
