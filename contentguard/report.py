"""
Turn scan results into (a) a readable console report and (b) a JSON evidence
record you can attach to a takedown notice.

Evidence that holds up: the matched original (title + path), the suspect URL,
the time offset where they line up, the hash-vote count, the video overlap, and
a UTC timestamp of when the match was found.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

_BAR = "-" * 64


def _fmt_candidate(c: dict) -> str:
    return (f"    [{c['verdict']:8}] conf={c['confidence']:5.1f}  "
            f"\"{c['title']}\" (work {c['work_id']})\n"
            f"               audio: {c['votes']} votes @ {c['offset_sec']}s into original | "
            f"video overlap: {c['video_overlap']*100:.0f}% "
            f"({c['video_frames_matched']} frames)")


def render(scan_result: dict) -> str:
    speed = scan_result.get("detected_speed", 1.0)
    speed_note = f"  (speed-corrected {speed}x)" if speed and abs(speed - 1.0) > 1e-6 else ""
    lines = [_BAR, f"SUSPECT: {scan_result['suspect']}",
             f"  platform={scan_result.get('platform', '?')}  "
             f"duration={scan_result['duration_sec']}s  "
             f"audio_hashes={scan_result['query_audio_hashes']}  "
             f"video_frames={scan_result['query_video_frames']}{speed_note}",
             f"  VERDICT: {scan_result['top_verdict']}"]
    if scan_result.get("top_verdict") == "ERROR":
        lines.append(f"    ! could not scan: {scan_result.get('error', 'unknown error')}")
        return "\n".join(lines)
    cands = scan_result.get("candidates") or []
    if not cands or scan_result["top_verdict"] == "NO MATCH":
        lines.append("    (no reference work matched above threshold)")
    for c in cands:
        if c["confidence"] <= 0 and c["votes"] == 0:
            continue
        lines.append(_fmt_candidate(c))
    return "\n".join(lines)


def render_all(scan_results) -> str:
    body = "\n".join(render(r) for r in scan_results)
    n_err = sum(r["top_verdict"] == "ERROR" for r in scan_results)
    summary = (f"\n{_BAR}\nSUMMARY: scanned {len(scan_results)} clip(s), "
               f"{sum(r['top_verdict']=='MATCH' for r in scan_results)} MATCH, "
               f"{sum(r['top_verdict']=='LIKELY' for r in scan_results)} LIKELY"
               + (f", {n_err} ERROR" if n_err else "") + f".\n{_BAR}")
    return body + summary


def evidence_record(scan_result: dict) -> dict:
    """A single suspect's evidence object (only confident candidates kept)."""
    confident = [c for c in scan_result.get("candidates", [])
                 if c["verdict"] in ("MATCH", "LIKELY")]
    return {
        "detected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "suspect": scan_result["suspect"],
        "platform": scan_result.get("platform"),
        "suspect_sha256": scan_result.get("sha256"),
        "suspect_duration_sec": scan_result["duration_sec"],
        "detected_speed": scan_result.get("detected_speed", 1.0),
        "verdict": scan_result["top_verdict"],
        "matches": [{
            "original_title": c["title"],
            "original_path": c["ref_path"],
            "confidence": c["confidence"],
            "audio_landmark_votes": c["votes"],
            "aligned_offset_sec": c["offset_sec"],
            "video_overlap_pct": round(c["video_overlap"] * 100, 1),
            "video_frames_matched": c["video_frames_matched"],
        } for c in confident],
        "method": "ContentGuard audio-landmark + perceptual-video-hash fingerprinting",
    }


def write_evidence(scan_results, out_path: str):
    records = [evidence_record(r) for r in scan_results
              if r["top_verdict"] in ("MATCH", "LIKELY")]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "ContentGuard",
        "total_scanned": len(scan_results),
        "total_flagged": len(records),
        "evidence": records,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_path
