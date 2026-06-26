"""
Ingest your *own* WOW TV catalog into the reference database. Run this on the
original masters / promos so the matcher knows what "yours" looks like.

Supports a single file or a directory (recurses common media extensions).
"""
from __future__ import annotations

import os

from . import config, media
from .db import FingerprintDB
from .fingerprint import audio as audio_fp
from .fingerprint import video as video_fp

MEDIA_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv",
              ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus"}


def ingest_file(db: FingerprintDB, path: str, title: str | None = None,
                do_video: bool = True, verbose: bool = True):
    title = title or os.path.splitext(os.path.basename(path))[0]
    duration = media.probe_duration(path)

    ahashes = audio_fp.fingerprint_file(path)
    work_id = db.add_work(title, path, duration, kind="reference")
    db.add_audio_hashes(work_id, ahashes)

    n_video = 0
    if do_video:
        try:
            vhashes = video_fp.fingerprint_file(path, include_flip=config.FLIP_INVARIANT)
            db.add_video_hashes(work_id, vhashes)
            n_video = len(vhashes)
        except Exception as e:  # noqa: BLE001  (video is optional, audio is enough)
            if verbose:
                print(f"  ! video fingerprint skipped ({e})")

    if verbose:
        print(f"  + [{work_id}] {title}  "
              f"({duration:.0f}s, {len(ahashes)} audio hashes, {n_video} video frames)")
    return work_id, len(ahashes), n_video


def _iter_media(path: str):
    if os.path.isfile(path):
        yield path
        return
    for root, _dirs, files in os.walk(path):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in MEDIA_EXTS:
                yield os.path.join(root, f)


def ingest_path(db: FingerprintDB, path: str, do_video: bool = True,
                verbose: bool = True):
    files = list(_iter_media(path))
    if not files:
        print(f"No media files found under {path}")
        return []
    print(f"Ingesting {len(files)} file(s) into {db.path} ...")
    results = []
    for f in files:
        try:
            results.append(ingest_file(db, f, do_video=do_video, verbose=verbose))
        except Exception as e:  # noqa: BLE001
            print(f"  ! FAILED {f}: {e}")
    s = db.stats()
    print(f"Done. DB now holds {s['works']} works, "
          f"{s['audio_hashes']} audio hashes, {s['video_hashes']} video frames.")
    return results
