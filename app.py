"""
WOW TV -- Piracy Finder (simple local website).
by Kratin Sharma

Run:
    cd "C:\\Users\\admin\\Desktop\\wowTV_title_privacy"
    python app.py
Then open http://127.0.0.1:8000  (khud-ba-khud browser khul jaayega).

Paste show names (one per line) -> get a table of flagged re-upload links +
a one-click CSV download. Uses the same engine as `contentguard discover`.
No extra install needed (Python's built-in web server).
"""
from __future__ import annotations

import base64
import csv
import html
import io
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from contentguard import discover as disc

# Local run -> 127.0.0.1:8000 (and auto-opens browser).
# Hosted run (Render/Railway set the PORT env var) -> bind 0.0.0.0:$PORT.
PORT = int(os.environ.get("PORT", "8000"))
HOSTED = "PORT" in os.environ
HOST = "0.0.0.0" if HOSTED else "127.0.0.1"

CSS = """<style>
 *{box-sizing:border-box}
 body{font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#1f2937;background:#f1f5f9}
 header{background:#0f172a;color:#fff;padding:20px 24px}
 header h1{margin:0;font-size:21px} header p{margin:6px 0 0;color:#cbd5e1;font-size:13px}
 .by{font-size:13px;font-weight:500;color:#93c5fd;letter-spacing:.02em}
 main{max-width:980px;margin:22px auto;padding:0 18px}
 form{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
 label{display:block;font-size:13px;font-weight:600;color:#334155;margin:0 0 5px}
 textarea,input{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;font-family:inherit}
 textarea{resize:vertical}
 .row{display:flex;gap:14px;margin-top:14px;flex-wrap:wrap}
 .row>div{flex:0 0 120px} .row>div.grow{flex:1 1 240px}
 .checks{display:flex;gap:20px;margin:14px 0 4px;flex-wrap:wrap}
 .checks label{display:flex;align-items:center;gap:7px;font-weight:500;cursor:pointer}
 .checks input{width:auto}
 button{margin-top:16px;background:#2563eb;color:#fff;border:0;padding:12px 22px;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}
 button:hover{background:#1d4ed8}
 .bar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px}
 .btn,.btn2{display:inline-block;padding:9px 16px;border-radius:8px;font-weight:600;text-decoration:none;font-size:14px}
 .btn{background:#16a34a;color:#fff} .btn2{background:#e2e8f0;color:#334155;margin-left:8px}
 table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);border-radius:10px;overflow:hidden}
 th,td{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #eef2f7;font-size:14px}
 th{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}
 tr.grp td{background:#f8fafc;border-top:2px solid #e2e8f0}
 .sc{font-weight:700;text-align:center;width:70px;color:#b45309}
 .ex{display:block;font-size:10px;font-weight:800;color:#fff;background:#b91c1c;border-radius:8px;padding:0 4px}
 .u{max-width:330px;word-break:break-all;font-size:12px} a{color:#2563eb} .mut{color:#94a3b8;font-size:12px}
 footer{text-align:center;color:#64748b;font-size:13px;padding:24px;font-style:italic}
 .overlay{display:none;position:fixed;inset:0;background:rgba(15,23,42,.75);color:#fff;align-items:center;justify-content:center;font-size:18px;text-align:center;padding:20px}
</style>"""


def esc(s):
    return html.escape(str(s))


def page(inner):
    return (f"<!doctype html><html lang=en><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'>"
            f"<title>WOW TV - Piracy Finder</title>{CSS}"
            f"<header><h1>WOW TV - Piracy Finder</h1>"
            f"<p>Enter show names, get the links where they have been re-uploaded, plus a CSV sheet.</p></header>"
            f"<main>{inner}</main><footer>by Kratin Sharma</footer></html>")


def form_html(shows="", threshold="60", limit="15", exclude="wowtv,kuku",
              translate=True, video=True, msg=""):
    tc = "checked" if translate else ""
    vc = "checked" if video else ""
    note = f"<p class=mut>{esc(msg)}</p>" if msg else ""
    return page(f"""{note}
<form method=post onsubmit="document.getElementById('load').style.display='flex'">
 <label>Shows (one show name per line)</label>
 <textarea name=shows rows=8 placeholder="Gymwala Billionaire&#10;Bhikhari Boss&#10;Banarasiya Mafia">{esc(shows)}</textarea>
 <div class=row>
  <div><label>Threshold</label><input name=threshold value="{esc(threshold)}"></div>
  <div><label>Limit</label><input name=limit value="{esc(limit)}"></div>
  <div class=grow><label>Hide your own channels</label><input name=exclude value="{esc(exclude)}"></div>
 </div>
 <div class=checks>
   <label><input type=checkbox name=translate {tc}> Regional translation (slower)</label>
   <label><input type=checkbox name=video {vc}> Video links only</label>
 </div>
 <button type=submit>Scan</button>
</form>
<div id=load class=overlay><div>Scanning...<br>about 10-20 seconds per show.<br>Please do not close this tab.</div></div>
""")


def to_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["show", "score", "exact", "platform", "channel", "found_title", "url"])
    w.writerows(rows)
    return buf.getvalue()


def results_html(groups, rows):
    csv_text = "﻿" + to_csv(rows)            # BOM -> Excel reads Hindi fine
    b64 = base64.b64encode(csv_text.encode("utf-8")).decode()
    blocks = []
    for show, items in groups:
        if not items:
            blocks.append(f"<tr class=grp><td colspan=4><b>{esc(show)}</b> "
                          f"<span class=mut>- nothing found</span></td></tr>")
            continue
        n_ex = sum(1 for r in items if r.get("exact"))
        tag = f" &middot; {n_ex} EXACT" if n_ex else ""
        blocks.append(f"<tr class=grp><td colspan=4><b>{esc(show)}</b> "
                      f"<span class=mut>- {len(items)} link(s){tag}</span></td></tr>")
        for r in items:
            ex = "<span class=ex>EXACT</span> " if r.get("exact") else ""
            link = (f"<a href='{esc(r['url'])}' target=_blank rel=noopener>{esc(r['url'])}</a>"
                    if r.get("url") else "-")
            blocks.append(f"<tr><td class=sc>{ex}{r['score']:.0f}</td>"
                          f"<td>{esc(r['platform'])}</td>"
                          f"<td>{esc(r['title'])}</td><td class=u>{link}</td></tr>")
    body = "".join(blocks) or "<tr><td colspan=4>Nothing flagged.</td></tr>"
    return page(f"""
<div class=bar>
  <div>{len(groups)} show(s) &middot; <b>{len(rows)}</b> flagged link(s)</div>
  <div>
    <a class=btn download="wowtv_leads.csv" href="data:text/csv;base64,{b64}">Download CSV</a>
    <a class=btn2 href="/">New scan</a>
  </div>
</div>
<table><tr><th>Score</th><th>Platform</th><th>Found title</th><th>Link</th></tr>{body}</table>
""")


def run_scans(shows, threshold, limit, exclude, translate, video):
    excl = [e.strip() for e in exclude.split(",") if e.strip()]
    groups, rows = [], []
    for name in shows:
        try:
            out = disc.discover(name, limit=limit, threshold=threshold, use_web=True,
                                exclude=excl, throttle=1.0, video_only=video,
                                translate=translate, sites=True)
            items = out["results"]
        except Exception as e:  # noqa: BLE001
            items = []
            print(f"  ! {name}: {e}")
        groups.append((name, items))
        for r in items:
            rows.append([name, f"{r['score']:.0f}", "YES" if r.get("exact") else "",
                         r["platform"], r.get("channel", ""), r["title"], r.get("url", "")])
    return groups, rows


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body):
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            self._send(form_html())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = parse_qs(self.rfile.read(n).decode("utf-8")) if n else {}
        shows = [s.strip() for s in data.get("shows", [""])[0].splitlines() if s.strip()]
        exclude = data.get("exclude", ["wowtv,kuku"])[0]
        translate = "translate" in data
        video = "video" in data
        try:
            threshold = float(data.get("threshold", ["60"])[0] or 60)
        except ValueError:
            threshold = 60.0
        try:
            limit = int(data.get("limit", ["20"])[0] or 20)
        except ValueError:
            limit = 20
        if not shows:
            self._send(form_html(exclude=exclude, translate=translate, video=video,
                                 msg="Please enter at least one show name."))
            return
        groups, rows = run_scans(shows, threshold, limit, exclude, translate, video)
        self._send(results_html(groups, rows))


def main():
    shown = f"http://127.0.0.1:{PORT}" if not HOSTED else f"http://{HOST}:{PORT}"
    print(f"\n  WOW TV Piracy Finder is running  ->  {shown}")
    print("  (press Ctrl+C in this window to stop)\n")
    if not HOSTED:
        try:
            threading.Timer(1.0, lambda: webbrowser.open(shown)).start()
        except Exception:  # noqa: BLE001
            pass
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
