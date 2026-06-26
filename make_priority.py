"""Build priority_shows.csv = the Live Tracker shows (currently-live originals,
highest piracy risk right now), language-deduped, for the deep AI scan."""
import csv
import re

seen = {}
with open("shows.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if "live_tracker" not in (r.get("sources") or ""):
            continue
        t = (r.get("title") or "").strip()
        if not t:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
        if key and key not in seen:
            seen[key] = r

rows = sorted(seen.values(), key=lambda r: r["title"].lower())
with open("priority_shows.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["title", "language", "show_id", "genre", "tropes", "sources"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"{len(rows)} live-tracker shows -> priority_shows.csv")
for r in rows:
    print(f"  - {r['title']}  ({r['language']}; {r['genre']}; {r['tropes']})")
