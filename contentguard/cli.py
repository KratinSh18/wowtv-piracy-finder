"""
ContentGuard command-line interface. Platform-agnostic: scan files, folders, or
URLs from ANY site (yt-dlp supports 1000+), and a watchlist of many at once.

  python -m contentguard selftest
  python -m contentguard ingest    <file|dir> [--no-video]
  python -m contentguard discover  "<show name>" | names.txt   [--save]   # search web by NAME
  python -m contentguard scan      <file|dir|url|list.txt> [--evidence out.json] [--save]
  python -m contentguard titlescan <file|url> [<file|url> ...] [--mine titles.txt]
  python -m contentguard cases     [--platform host] [--export out.csv|out.json]
  python -m contentguard works
  python -m contentguard rm        <work_id>
  python -m contentguard wm-embed  <in> <out> --id N [--video]
  python -m contentguard wm-detect <in> [--video]
"""
from __future__ import annotations

import argparse
import os
import sys

from . import config


def _db(args):
    from .db import FingerprintDB
    return FingerprintDB(args.db)


def cmd_selftest(args):
    from . import selftest
    return selftest.run()


def cmd_ingest(args):
    from . import ingest
    db = _db(args)
    ingest.ingest_path(db, args.path, do_video=not args.no_video)
    return 0


def cmd_scan(args):
    from . import report, scan
    db = _db(args)
    results = scan.scan_path(db, args.path, do_video=not args.no_video, top=args.top,
                             speed_search=not args.no_speed_search)
    print(report.render_all(results))

    if args.save:
        saved = 0
        for r in results:
            if r["top_verdict"] in ("MATCH", "LIKELY") and r.get("candidates"):
                c = r["candidates"][0]
                db.add_detection({
                    "source": r["suspect"], "platform": r.get("platform"),
                    "work_id": c["work_id"], "matched_title": c.get("title"),
                    "verdict": r["top_verdict"], "confidence": c["confidence"],
                    "offset_sec": c["offset_sec"], "video_overlap": c["video_overlap"],
                    "detected_speed": r.get("detected_speed", 1.0),
                    "sha256": r.get("sha256"),
                })
                saved += 1
        print(f"\nSaved {saved} detection(s) to the case log (`contentguard cases` to view).")

    if args.evidence:
        path = report.write_evidence(results, args.evidence)
        flagged = sum(r["top_verdict"] in ("MATCH", "LIKELY") for r in results)
        print(f"Evidence for {flagged} flagged clip(s) written to {path}")
    return 0


def cmd_cases(args):
    import csv as _csv
    import json as _json
    db = _db(args)
    rows = db.list_detections(platform=args.platform)
    if not rows:
        print("No detections saved yet. Run `scan --save` to build the case log.")
        return 0

    if args.export:
        if args.export.lower().endswith(".json"):
            with open(args.export, "w", encoding="utf-8") as f:
                _json.dump(rows, f, indent=2, ensure_ascii=False)
        else:
            with open(args.export, "w", newline="", encoding="utf-8") as f:
                w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        print(f"Exported {len(rows)} detection(s) to {args.export}")
        return 0

    by_platform = {}
    for r in rows:
        by_platform.setdefault(r["platform"] or "?", []).append(r)
    print(f"{len(rows)} detection(s) across {len(by_platform)} platform(s):\n")
    for plat, items in sorted(by_platform.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{plat}]  ({len(items)})")
        for r in items:
            print(f"     {r['verdict']:6} conf={r['confidence']:5.1f}  "
                  f"\"{r['matched_title']}\"  <- {r['source']}")
    return 0


def cmd_works(args):
    db = _db(args)
    works = db.list_works()
    if not works:
        print("(no works ingested yet)")
        return 0
    s = db.stats()
    print(f"{s['works']} works | {s['audio_hashes']} audio hashes | "
          f"{s['video_hashes']} video frames\n")
    for w in works:
        print(f"  [{w['id']:>4}] {w['title']}  ({w['duration']:.0f}s)  {w['path']}")
    return 0


def cmd_rm(args):
    db = _db(args)
    w = db.get_work(args.work_id)
    if not w:
        print(f"No work with id {args.work_id}")
        return 1
    db.remove_work(args.work_id)
    print(f"Removed [{args.work_id}] {w['title']}")
    return 0


def cmd_discover(args):
    from . import discover as disc
    from . import media

    # one name, or a .txt/.csv of many show names
    names = [args.name]
    if (not media.is_url(args.name) and os.path.isfile(args.name)
            and args.name.lower().endswith((".txt", ".csv"))):
        from . import titlematch
        names = titlematch.load_titles(args.name)

    platforms = tuple(p.strip() for p in args.platforms.split(",") if p.strip())
    exclude = [e.strip() for e in (args.exclude or "").split(",") if e.strip()]
    db = _db(args) if args.save else None
    any_hit = False
    outs = []

    langs = [l.strip() for l in (args.langs or "").split(",") if l.strip()]
    for nm in names:
        out = disc.discover(nm, limit=args.limit, threshold=args.threshold,
                            platforms=platforms, use_web=not args.no_web,
                            exclude=exclude, throttle=args.throttle,
                            video_only=not args.all_links,
                            translate=not args.no_translate, langs=langs,
                            sites=not args.no_sites,
                            check_live=not args.no_live_check)
        outs.append(out)
        kind = "video links only" if out["video_only"] else "all links"
        tr = " +translations" if out["translated"] else ""
        print(f"\n=== \"{nm}\"  ({len(out['variants'])} variants{tr}; "
              f"{out['web_backends']}; {kind}) ===")
        if not out["results"]:
            print("   no video re-uploads found")
            continue
        any_hit = True
        n_exact = sum(1 for r in out["results"] if r.get("exact"))
        print(f"   {len(out['results'])} video lead(s) ({n_exact} EXACT) "
              "-- EXACT first; open the link to verify:")
        for r in out["results"]:
            tag = "EXACT " if r.get("exact") else "      "
            concept = ("  [" + ", ".join(r["shared"]) + "]") if r["shared"] else ""
            print(f"     {tag}{r['score']:5.1f}  [{r['platform']}]{concept}")
            print(f"            \"{r['title']}\"")
            if r["url"]:
                print(f"            {r['url']}")
            if db:
                db.add_detection({
                    "source": r["url"] or r["title"], "platform": r["platform"],
                    "work_id": 0, "matched_title": nm,  # 0 = title-only lead (no fingerprint work)
                    "verdict": "WEB-LEAD", "confidence": r["score"],
                    "offset_sec": None, "video_overlap": None,
                    "detected_speed": None, "sha256": None,
                })

    if args.report:
        html_str = disc.render_html(outs, threshold=args.threshold, exclude=exclude)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(html_str)
        print(f"\nHTML report written to {args.report}  (open it in a browser).")

    if args.json:
        import json as _json
        keys = ("score", "exact", "platform", "channel", "title", "url", "snippet", "shared")
        payload = {"shows": [
            {"show": o["name"],
             "results": [{k: r.get(k) for k in keys} for r in o["results"]]}
            for o in outs]}
        with open(args.json, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"\nJSON leads written to {args.json}.")

    if not any_hit:
        print("\n(Tip: lower --threshold, raise --limit. Whole-web (DuckDuckGo) is "
              "keyless; add GOOGLE_API_KEY + GOOGLE_CSE_ID for extra recall.)")
    elif db:
        print("\nLeads saved to the case log (`contentguard cases`).")
    return 0


def cmd_titlescan(args):
    from . import media, titlematch
    db = _db(args)

    # your catalog titles: from --mine file/url, else from the ingested DB
    if args.mine:
        catalog = titlematch.load_titles(args.mine)
    else:
        catalog = [w["title"] for w in db.list_works()]
    if not catalog:
        print("No catalog titles. Ingest your content first, or pass --mine <file>.")
        return 1

    # pull rival titles from one OR MANY sources (files / URLs across platforms),
    # tagging each title with where it came from.
    rival = []
    for src in args.source:
        label = media.platform_of(src) if media.is_url(src) else os.path.basename(src)
        try:
            for t in titlematch.load_titles(src):
                rival.append((t, label))
        except Exception as e:  # noqa: BLE001
            print(f"  ! skipped source {src}: {e}")

    hits = titlematch.best_matches(rival, catalog, threshold=args.threshold)
    print(f"Compared {len(rival)} rival title(s) from {len(args.source)} source(s) "
          f"against {len(catalog)} of yours (threshold {args.threshold}).\n")
    if not hits:
        print("No suspicious title matches above threshold.")
        return 0
    print(f"{len(hits)} SUSPICIOUS title(s) -- confirm each with `scan` before acting:\n")
    for h in hits:
        concepts = (" via [" + ", ".join(h["shared_concepts"]) + "]") if h["shared_concepts"] else ""
        src = f"  [{h['rival_source']}]" if h.get("rival_source") else ""
        print(f"  {h['score']:5.1f}  \"{h['rival_title']}\"{src}")
        print(f"         ~= your \"{h['matched_catalog_title']}\""
              f"  (synonym {h['synonym_overlap']} / fuzzy {h['fuzzy']}){concepts}")
    print("\nNext: download each suspicious clip and run "
          "`python -m contentguard scan <clip> --save` to CONFIRM with the fingerprint engine.")
    return 0


def cmd_wm_embed(args):
    from . import watermark
    if args.video:
        watermark.embed_video(args.input, args.output, args.id)
    else:
        watermark.embed_image_file(args.input, args.output, args.id)
    print(f"Embedded id={args.id} -> {args.output}")
    return 0


def cmd_wm_detect(args):
    from . import watermark
    res = (watermark.extract_video(args.input) if args.video
           else watermark.extract_image_file(args.input))
    if res["present"]:
        print(f"WATERMARK FOUND: id={res['id']} (0x{res['id']:08X})  "
              f"confidence={res['confidence']}")
    else:
        print(f"No ContentGuard watermark detected (confidence={res['confidence']}).")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="contentguard",
        description="ContentGuard -- catch your micro-dramas re-uploaded on rival platforms.")
    p.add_argument("--db", default=config.DB_DEFAULT, help="fingerprint database path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("selftest", help="prove the engine works on synthetic data")
    sp.set_defaults(func=cmd_selftest)

    sp = sub.add_parser("ingest", help="add your own content to the reference DB")
    sp.add_argument("path")
    sp.add_argument("--no-video", action="store_true", help="audio fingerprint only")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("scan",
                        help="check a suspect file / folder / URL / watchlist (.txt|.csv of many) against the DB")
    sp.add_argument("path", help="a media file, a folder, a URL (any site), or a .txt/.csv list of them")
    sp.add_argument("--no-video", action="store_true")
    sp.add_argument("--no-speed-search", action="store_true",
                    help="skip multi-speed audio search (faster, but misses speed-altered rips)")
    sp.add_argument("--save", action="store_true",
                    help="persist MATCH/LIKELY hits to the case log (dedup per source+work)")
    sp.add_argument("--top", type=int, default=5)
    sp.add_argument("--evidence", help="write JSON evidence (incl. SHA-256) for flagged clips here")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("cases", help="list / export saved detections across all platforms")
    sp.add_argument("--platform", help="filter to one platform/host")
    sp.add_argument("--export", help="write the case log to a .csv or .json file")
    sp.set_defaults(func=cmd_cases)

    sp = sub.add_parser("works", help="list ingested reference works")
    sp.set_defaults(func=cmd_works)

    sp = sub.add_parser("discover",
                        help="search the WHOLE WEB by show name to find where it's re-uploaded (no download)")
    sp.add_argument("name", help="a show name, or a .txt/.csv of many show names")
    sp.add_argument("--limit", type=int, default=20, help="results per query (default 20)")
    sp.add_argument("--threshold", type=float, default=50.0,
                    help="min title similarity 0-100 to report (default 50)")
    sp.add_argument("--platforms", default="youtube",
                    help="comma list of yt-dlp platforms to also search (default youtube)")
    sp.add_argument("--no-web", action="store_true",
                    help="skip the whole-web (DuckDuckGo) sweep; search yt-dlp platforms only")
    sp.add_argument("--throttle", type=float, default=1.0,
                    help="seconds between web queries to avoid DuckDuckGo rate-limit (default 1.0)")
    sp.add_argument("--report", help="write a clickable HTML report of all leads to this path")
    sp.add_argument("--json", help="write all leads as structured JSON to this path")
    sp.add_argument("--no-translate", action="store_true",
                    help="don't also search regional-language (Tamil/Telugu/...) translations of the title")
    sp.add_argument("--langs", default="hi,ta,te,kn,ml",
                    help="languages to translate the title into (default hi,ta,te,kn,ml)")
    sp.add_argument("--all-links", action="store_true",
                    help="include non-video (script/text) links too (default: VIDEO links only)")
    sp.add_argument("--no-sites", action="store_true",
                    help="skip the direct Moj/ShareChat/Dailymotion site-scoped probes")
    sp.add_argument("--no-live-check", action="store_true",
                    help="don't verify links are live / drop removed videos (faster)")
    sp.add_argument("--exclude", default="",
                    help="comma list of channel/platform/url substrings to hide (e.g. your own: \"wow tv,wowtv,kuku\")")
    sp.add_argument("--save", action="store_true", help="log leads to the case log")
    sp.set_defaults(func=cmd_discover)

    sp = sub.add_parser("titlescan",
                        help="flag rival titles that are synonym/fuzzy renames of your shows")
    sp.add_argument("source", nargs="+",
                    help="one or MANY rival sources: .txt (one/line), .csv (title column), or channel/playlist URLs")
    sp.add_argument("--mine",
                    help="your titles (.txt/.csv/url); default = titles already ingested in the DB")
    sp.add_argument("--threshold", type=float, default=55.0,
                    help="min similarity 0-100 to flag (default 55)")
    sp.set_defaults(func=cmd_titlescan)

    sp = sub.add_parser("rm", help="remove a work from the DB")
    sp.add_argument("work_id", type=int)
    sp.set_defaults(func=cmd_rm)

    sp = sub.add_parser("wm-embed", help="embed an invisible forensic watermark")
    sp.add_argument("input")
    sp.add_argument("output")
    sp.add_argument("--id", type=int, required=True, help="32-bit payload id")
    sp.add_argument("--video", action="store_true")
    sp.set_defaults(func=cmd_wm_embed)

    sp = sub.add_parser("wm-detect", help="detect/extract a forensic watermark")
    sp.add_argument("input")
    sp.add_argument("--video", action="store_true")
    sp.set_defaults(func=cmd_wm_detect)

    return p


def _force_utf8():
    # Windows consoles default to cp1252 and crash on Hindi/Unicode titles or a
    # stray BOM. Force UTF-8 output so non-Latin titles print safely.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main(argv=None):
    _force_utf8()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
