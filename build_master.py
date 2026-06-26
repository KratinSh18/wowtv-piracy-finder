"""
master_leads.json (discover --json output) -> ek saaf master sheet:
  master_report.html  (browser mein khol ke dekho, clickable links)
  master_leads.csv    (Excel / Google Sheets mein khol lo)

Run:  python build_master.py
by Kratin Sharma
"""
from __future__ import annotations

import csv
import html
import json
import os

SRC = "master_leads.json"


def esc(s):
    return html.escape(str(s if s is not None else ""))


def color(score):
    return "#b91c1c" if score >= 85 else "#c2410c" if score >= 65 else "#a16207"


def main():
    if not os.path.exists(SRC):
        print(f"{SRC} nahi mila. Pehle: python -m contentguard discover top_shows.txt --json {SRC}")
        return
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    shows = data.get("shows", [])

    # ---- CSV ----
    rows = 0
    with open("master_leads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["show", "score", "exact", "platform", "channel", "found_title", "url"])
        for s in shows:
            for r in s.get("results", []):
                w.writerow([s["show"], round(r.get("score", 0)), "YES" if r.get("exact") else "",
                            r.get("platform", ""), r.get("channel", ""), r.get("title", ""), r.get("url", "")])
                rows += 1

    # ---- HTML ----
    total = rows
    exact_total = sum(1 for s in shows for r in s.get("results", []) if r.get("exact"))
    blocks = []
    for s in shows:
        res = s.get("results", [])
        nm = esc(s["show"])
        if not res:
            blocks.append(f"<tr class=grp><td colspan=4><b>{nm}</b> "
                          f"<span class=mut>&mdash; kuch nahi mila</span></td></tr>")
            continue
        nex = sum(1 for r in res if r.get("exact"))
        tag = f" &middot; {nex} EXACT" if nex else ""
        blocks.append(f"<tr class=grp><td colspan=4><b>{nm}</b> "
                      f"<span class=mut>&mdash; {len(res)} link(s){tag}</span></td></tr>")
        for r in res:
            sc = r.get("score", 0)
            ex = "<span class=ex>EXACT</span> " if r.get("exact") else ""
            url = r.get("url", "")
            link = f"<a href='{esc(url)}' target=_blank rel=noopener>{esc(url)}</a>" if url else "&mdash;"
            blocks.append(f"<tr><td class=sc style='color:{color(sc)}'>{ex}{sc:.0f}</td>"
                          f"<td>{esc(r.get('platform',''))}</td>"
                          f"<td>{esc(r.get('title',''))}</td><td class=u>{link}</td></tr>")
    body = "".join(blocks) or "<tr><td colspan=4>Kuch flag nahi hua.</td></tr>"
    page = f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>WOW TV - Master Piracy Sheet</title>
<style>
 body{{font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#1f2937;background:#f1f5f9}}
 header{{background:#0f172a;color:#fff;padding:20px 24px}} header h1{{margin:0;font-size:21px}}
 header p{{margin:6px 0 0;color:#cbd5e1;font-size:13px}}
 main{{max-width:1000px;margin:22px auto;padding:0 18px}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);border-radius:10px;overflow:hidden}}
 th,td{{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #eef2f7;font-size:14px}}
 th{{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}}
 tr.grp td{{background:#f8fafc;border-top:2px solid #e2e8f0}}
 .sc{{font-weight:700;text-align:center;width:66px}}
 .ex{{display:block;font-size:10px;font-weight:800;color:#fff;background:#b91c1c;border-radius:8px;padding:0 4px}}
 .u{{max-width:340px;word-break:break-all;font-size:12px}} a{{color:#2563eb}} .mut{{color:#94a3b8;font-size:12px}}
 footer{{text-align:center;color:#64748b;font-size:13px;padding:24px;font-style:italic}}
</style>
<header><h1>WOW TV - Master Piracy Sheet</h1>
<p>{len(shows)} shows &middot; <b>{total}</b> flagged video link(s) &middot; {exact_total} EXACT &middot; EXACT sabse upar</p></header>
<main>
<table><tr><th>Score</th><th>Platform</th><th>Found title</th><th>Link</th></tr>{body}</table>
</main>
<footer>by Kratin Sharma</footer></html>"""
    with open("master_report.html", "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Done: master_report.html + master_leads.csv  ({total} links across {len(shows)} shows, {exact_total} EXACT)")


if __name__ == "__main__":
    main()
