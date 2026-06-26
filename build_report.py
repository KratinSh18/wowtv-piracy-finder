"""
Turn the AI piracy-hunt results (suspects.json) into a clickable HTML report
+ a CSV you can file/track. Grouped by show, STRONG leads first.

    python build_report.py suspects.json
-> writes piracy_report.html  and  piracy_report.csv
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import defaultdict

RANK = {"STRONG": 0, "POSSIBLE": 1, "NOISE": 2}
BADGE = {"STRONG": "#b91c1c", "POSSIBLE": "#c2410c", "NOISE": "#94a3b8"}


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("suspects", []), data.get("stats", {})
    return data, {}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "suspects.json"
    suspects, stats = load(path)
    # show NOISE too in the CSV, but the HTML highlights STRONG/POSSIBLE
    suspects.sort(key=lambda s: (RANK.get(s.get("verdict", "NOISE"), 3),
                                 -float(s.get("confidence", 0) or 0)))

    # ---- CSV (everything, for your records / takedown tracker) ----
    cols = ["verdict", "confidence", "show_title", "found_title", "platform",
            "channel", "url", "reason"]
    with open("piracy_report.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for s in suspects:
            w.writerow(s)

    # ---- HTML (STRONG + POSSIBLE, grouped by show) ----
    strong = [s for s in suspects if s.get("verdict") == "STRONG"]
    possible = [s for s in suspects if s.get("verdict") == "POSSIBLE"]
    shown = strong + possible
    by_show = defaultdict(list)
    for s in shown:
        by_show[s.get("show_title", "?")].append(s)
    # order shows by their best (lowest rank, highest confidence) lead
    order = sorted(by_show.items(),
                   key=lambda kv: (RANK.get(kv[1][0].get("verdict"), 3),
                                   -float(kv[1][0].get("confidence", 0) or 0)))
    esc = html.escape

    blocks = []
    for show, items in order:
        rows = []
        for s in items:
            v = s.get("verdict", "?")
            rows.append(
                "<tr>"
                f'<td><span class="badge" style="background:{BADGE.get(v, "#999")}">{esc(v)}</span></td>'
                f'<td class="conf">{int(float(s.get("confidence", 0) or 0))}</td>'
                f'<td><span class="host">{esc(s.get("platform", ""))}</span>'
                f'{("<br><span class=mut>" + esc(s.get("channel", "")) + "</span>") if s.get("channel") else ""}</td>'
                f'<td><div class="ft">{esc(s.get("found_title", ""))}</div>'
                f'<div class="rsn">{esc(s.get("reason", ""))}</div></td>'
                f'<td class="u">{(chr(60) + "a href=" + chr(34) + esc(s.get("url", "")) + chr(34) + " target=_blank rel=noopener>" + esc(s.get("url", "")) + "</a>") if s.get("url") else "—"}</td>'
                "</tr>")
        n_strong = sum(1 for s in items if s.get("verdict") == "STRONG")
        tag = f'<span class="cnt strong">{n_strong} STRONG</span>' if n_strong else ""
        blocks.append(
            f'<tr class="grp"><td colspan="5"><b>{esc(show)}</b> '
            f'<span class="mut">— {len(items)} lead(s)</span> {tag}</td></tr>'
            + "".join(rows))

    nshows = stats.get("shows", "?")
    summary = (f'{len(strong)} STRONG · {len(possible)} POSSIBLE · '
               f'{stats.get("noise", "?")} filtered as noise · '
               f'{nshows} shows scanned')
    body = "".join(blocks) or '<tr><td colspan="5">No STRONG/POSSIBLE leads — only noise was found.</td></tr>'
    htmlpage = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WOW TV — piracy leads</title>
<style>
 body{{font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#1f2937;background:#f8fafc}}
 header{{background:#0f172a;color:#fff;padding:18px 22px}} header h1{{margin:0;font-size:20px}}
 header p{{margin:6px 0 0;color:#cbd5e1;font-size:13px}}
 .wrap{{padding:18px 22px}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08);border-radius:8px;overflow:hidden}}
 th,td{{padding:9px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #eef2f7}}
 th{{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}}
 tr.grp td{{background:#f8fafc;border-top:2px solid #e2e8f0}}
 .badge{{color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}}
 .conf{{font-weight:700;text-align:center;width:42px}}
 .host{{font-weight:600}} .mut{{color:#94a3b8;font-size:12px}}
 .ft{{font-weight:500}} .rsn{{color:#64748b;font-size:12px;margin-top:2px}}
 .u{{max-width:330px;word-break:break-all;font-size:12px}} a{{color:#2563eb}}
 .cnt{{font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px}}
 .cnt.strong{{background:#fee2e2;color:#b91c1c}}
 footer{{padding:14px 22px;color:#94a3b8;font-size:12px}}
</style>
<header><h1>🛡️ WOW TV — AI piracy leads (title-level)</h1>
<p>{esc(summary)}</p></header>
<div class="wrap"><table>
<tr><th>Verdict</th><th>Conf</th><th>Where</th><th>Found title / why</th><th>Link</th></tr>
{body}
</table>
<footer>A title match is a <b>LEAD, not proof</b>. Open each link to eyeball it; for a takedown, download that one clip and confirm by fingerprint
(<code>python -m contentguard scan &lt;url&gt;</code>). Full classified list incl. noise is in <b>piracy_report.csv</b>.</footer>
</div></html>"""
    with open("piracy_report.html", "w", encoding="utf-8") as f:
        f.write(htmlpage)

    print(f"Wrote piracy_report.html ({len(strong)} STRONG + {len(possible)} POSSIBLE) "
          f"and piracy_report.csv ({len(suspects)} total rows).")


if __name__ == "__main__":
    main()
