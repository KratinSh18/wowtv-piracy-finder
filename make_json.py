import csv, json
shows = []
with open("priority_shows.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        t = (r.get("title") or "").strip()
        if t:
            shows.append({"title": t,
                          "language": (r.get("language") or "").strip(),
                          "genre": (r.get("genre") or "").strip(),
                          "tropes": (r.get("tropes") or "").strip()})
with open("priority_shows.json", "w", encoding="utf-8") as f:
    json.dump(shows, f, ensure_ascii=False)
print(f"wrote {len(shows)} shows to priority_shows.json")
