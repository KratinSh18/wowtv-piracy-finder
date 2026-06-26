"""
Build the AI-VERIFIED master report from the verify-workflow output.

    python build_verified.py verified_leads.json
-> writes verified_report.html  and  verified_leads.csv

Verdicts (set by the AI verifier):
  CONFIRMED  - almost certainly YOUR show re-uploaded on a 3rd-party video host
  LIKELY     - strong lead, eyeball it
  PROMO      - mentions WoW TV / affiliate-marketing (points back to you, not piracy)
  DIFFERENT  - a different show that merely shares trope words
  NOISE      - unrelated
by Kratin Sharma
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import defaultdict

RANK = {"CONFIRMED": 0, "LIKELY": 1, "PROMO": 2, "DIFFERENT": 3, "NOISE": 4}
COLOR = {"CONFIRMED": "#b91c1c", "LIKELY": "#c2410c", "PROMO": "#2563eb",
         "DIFFERENT": "#94a3b8", "NOISE": "#94a3b8"}
SHOW_IN_HTML = {"CONFIRMED", "LIKELY", "PROMO"}


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("leads", data) if isinstance(data, dict) else data


def esc(s):
    return html.escape(str(s if s is not None else ""))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "verified_leads.json"
    leads = load(path)
    for ld in leads:
        ld["_r"] = RANK.get(ld.get("verdict", "NOISE"), 5)
    leads.sort(key=lambda l: (l["_r"], -float(l.get("confidence", 0) or 0)))

    # ---- CSV: everything, with verdict (for your records / takedowns) ----
    cols = ["verdict", "confidence", "show", "found_title", "platform", "channel", "url", "reason"]
    with open("verified_leads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for l in leads:
            w.writerow(l)

    # ---- HTML: CONFIRMED + LIKELY + PROMO, grouped by show ----
    shown = [l for l in leads if l.get("verdict") in SHOW_IN_HTML]
    by_show = defaultdict(list)
    for l in shown:
        by_show[l.get("show", "?")].append(l)
    order = sorted(by_show.items(),
                   key=lambda kv: (kv[1][0]["_r"], -float(kv[1][0].get("confidence", 0) or 0)))

    n_conf = sum(1 for l in leads if l.get("verdict") == "CONFIRMED")
    n_like = sum(1 for l in leads if l.get("verdict") == "LIKELY")
    n_promo = sum(1 for l in leads if l.get("verdict") == "PROMO")

    blocks = []
    for show, items in order:
        c = sum(1 for l in items if l.get("verdict") == "CONFIRMED")
        tag = f'<span class=cnt>{c} CONFIRMED</span>' if c else ""
        blocks.append(f'<tr class=grp><td colspan=5><b>{esc(show)}</b> '
                      f'<span class=mut>&mdash; {len(items)} lead(s)</span> {tag}</td></tr>')
        for l in items:
            v = l.get("verdict", "?")
            link = (f'<a href="{esc(l.get("url"))}" target=_blank rel=noopener>{esc(l.get("url"))}</a>'
                    if l.get("url") else "&mdash;")
            blocks.append(
                "<tr>"
                f'<td><span class=badge style="background:{COLOR.get(v, "#999")}">{esc(v)}</span></td>'
                f'<td class=cf>{int(float(l.get("confidence", 0) or 0))}</td>'
                f'<td><div class=ft>{esc(l.get("found_title"))}</div>'
                f'<div class=rsn>{esc(l.get("reason"))}</div></td>'
                f'<td>{esc(l.get("platform"))}<br><span class=mut>{esc(l.get("channel"))}</span></td>'
                f'<td class=u>{link}</td></tr>')
    body = "".join(blocks) or "<tr><td colspan=5>Koi confirmed/likely re-upload nahi mila.</td></tr>"

    page = f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>WOW TV - AI-Verified Piracy Report</title>
<style>
 body{{font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#1f2937;background:#f1f5f9}}
 header{{background:#0f172a;color:#fff;padding:20px 24px}} header h1{{margin:0;font-size:21px}}
 header p{{margin:8px 0 0;color:#cbd5e1;font-size:13px}}
 .k{{display:inline-block;background:#1e293b;border-radius:8px;padding:4px 10px;margin:4px 6px 0 0;font-size:13px}}
 main{{max-width:1040px;margin:22px auto;padding:0 18px}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);border-radius:10px;overflow:hidden}}
 th,td{{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #eef2f7;font-size:14px}}
 th{{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}}
 tr.grp td{{background:#f8fafc;border-top:2px solid #e2e8f0}}
 .badge{{color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}}
 .cf{{font-weight:700;text-align:center;width:44px}} .cnt{{font-size:11px;font-weight:700;background:#fee2e2;color:#b91c1c;padding:1px 7px;border-radius:9px}}
 .ft{{font-weight:500}} .rsn{{color:#64748b;font-size:12px;margin-top:2px}} .mut{{color:#94a3b8;font-size:12px}}
 .u{{max-width:300px;word-break:break-all;font-size:12px}} a{{color:#2563eb}}
 .btn{{display:inline-block;margin-top:12px;background:#16a34a;color:#fff;padding:9px 16px;border-radius:8px;font-weight:600;text-decoration:none}}
 footer{{text-align:center;color:#64748b;font-size:13px;padding:24px;font-style:italic}}
</style>
<header>
 <h1>&#128737;&#65039; WOW TV &mdash; AI-Verified Piracy Report</h1>
 <p>Har lead ko AI ne verify kiya hai. CONFIRMED = pakka re-upload, LIKELY = dekh lo, PROMO = WoW TV ka naam le raha (affiliate).</p>
 <div><span class=k>&#128308; {n_conf} CONFIRMED</span><span class=k>&#128992; {n_like} LIKELY</span><span class=k>&#128309; {n_promo} PROMO</span></div>
</header>
<main>
 <a class=btn download="verified_leads.csv" href="verified_leads.csv">&#11015; CSV sheet download</a>
 <table style="margin-top:14px">
  <tr><th>Verdict</th><th>Conf</th><th>Found title / AI reason</th><th>Where</th><th>Link</th></tr>
  {body}
 </table>
</main>
<footer>by Kratin Sharma</footer></html>"""
    with open("verified_report.html", "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote verified_report.html ({n_conf} CONFIRMED, {n_like} LIKELY, "
          f"{n_promo} PROMO) and verified_leads.csv ({len(leads)} rows).")


if __name__ == "__main__":
    main()
