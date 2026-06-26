"""
The matching engine: turn fingerprints + the reference DB into ranked,
scored verdicts.

Two-stage design (cheap signal narrows, expensive signal confirms):
  1. AUDIO match against the indexed landmark DB -> a short list of candidate
     works, each with a vote count at a single consistent time offset.
  2. VIDEO match only against those candidates -> fraction of suspect frames
     that perceptually match the work.
  3. Combine into a 0..100 confidence and a verdict (MATCH / LIKELY / NO MATCH).
"""
from __future__ import annotations

from collections import defaultdict

from . import config
from .fingerprint import audio as audio_fp
from .fingerprint import video as video_fp


def audio_match(query_hashes, db, top: int = 5):
    """Return ranked [{work_id, votes, offset_frames, offset_sec}] for a query."""
    qmap = defaultdict(list)
    for h, t in query_hashes:
        qmap[h].append(t)

    lookup = db.lookup_audio_batch(qmap.keys())

    votes = defaultdict(lambda: defaultdict(int))  # work_id -> {offset: count}
    for h, tqs in qmap.items():
        for (work_id, t_ref) in lookup.get(int(h), ()):  # noqa: SIM118
            for tq in tqs:
                votes[work_id][t_ref - tq] += 1

    tol = config.OFFSET_TOLERANCE
    results = []
    for work_id, offset_counts in votes.items():
        # Tolerance binning: re-encode/STFT-boundary jitter spreads a true hit
        # across adjacent offsets, so score the best +-tol window, not one bin.
        best_offset, best_votes = 0, 0
        for o in offset_counts:
            v = sum(offset_counts.get(o + d, 0) for d in range(-tol, tol + 1))
            if v > best_votes:
                best_votes, best_offset = v, o
        results.append({
            "work_id": work_id,
            "votes": int(best_votes),
            "offset_frames": int(best_offset),
            "offset_sec": round(audio_fp.frames_to_seconds(best_offset), 2),
            "total_query_hashes": len(query_hashes),
        })
    results.sort(key=lambda r: -r["votes"])
    return results[:top]


def video_match(query_phashes, db, work_id: int):
    """Fraction of suspect frames matching some frame of `work_id`."""
    ref = db.video_hashes(work_id)
    if not ref or not query_phashes:
        return 0.0, 0
    ref_hashes = [h for _, h in ref]
    matched = 0
    for _, hq in query_phashes:
        best = min((video_fp.hamming(hq, hr) for hr in ref_hashes), default=64)
        if best <= config.VIDEO_MAX_HAMMING:
            matched += 1
    return matched / len(query_phashes), matched


def _confidence(votes: int, video_frac: float, video_matched: int = 0) -> float:
    """Blend audio votes and video overlap into a 0..100 confidence."""
    # Audio saturates: MIN_AUDIO_MATCH votes already = strong evidence.
    audio_c = min(1.0, votes / (config.MIN_AUDIO_MATCH * 2.5))
    # Video is containment-aware: a high overlap OR enough absolute matched
    # frames both corroborate, so a short stolen clip buried in a long
    # compilation (low whole-file fraction) still counts.
    video_frac_c = video_frac / max(config.VIDEO_MATCH_FRAC, 1e-6)
    video_abs_c = video_matched / max(config.MIN_VIDEO_FRAMES, 1)
    video_c = min(1.0, max(video_frac_c, video_abs_c))
    # Audio is the trustworthy primary; video is corroboration. A strong audio
    # hit alone should already flag; video can only push it higher.
    combined = 0.7 * audio_c + 0.3 * video_c
    # Bonus when both agree (two independent signals -> much harder to be chance)
    if audio_c > 0.5 and video_c > 0.5:
        combined = min(1.0, combined + 0.15)
    return round(100.0 * combined, 1)


def verdict(confidence: float) -> str:
    if confidence >= config.VERDICT_MATCH:
        return "MATCH"
    if confidence >= config.VERDICT_LIKELY:
        return "LIKELY"
    return "NO MATCH"


def match(query_audio_hashes, query_video_phashes, db, top: int = 5):
    """Full pipeline for one suspect clip. Returns ranked candidate dicts."""
    candidates = audio_match(query_audio_hashes, db, top=top)

    # Seed video-only candidates too, in case audio was stripped/replaced.
    seen = {c["work_id"] for c in candidates}
    if query_video_phashes and len(candidates) < top:
        for w in db.list_works():
            if w["id"] not in seen:
                candidates.append({
                    "work_id": w["id"], "votes": 0,
                    "offset_frames": 0, "offset_sec": 0.0,
                    "total_query_hashes": len(query_audio_hashes),
                })
                seen.add(w["id"])
                if len(candidates) >= top:
                    break

    out = []
    for c in candidates:
        vfrac, vmatched = (0.0, 0)
        if query_video_phashes:
            vfrac, vmatched = video_match(query_video_phashes, db, c["work_id"])
        conf = _confidence(c["votes"], vfrac, vmatched)
        work = db.get_work(c["work_id"]) or {}
        out.append({
            **c,
            "title": work.get("title"),
            "ref_path": work.get("path"),
            "video_overlap": round(vfrac, 3),
            "video_frames_matched": vmatched,
            "confidence": conf,
            "verdict": verdict(conf),
        })
    out.sort(key=lambda r: -r["confidence"])
    return out
