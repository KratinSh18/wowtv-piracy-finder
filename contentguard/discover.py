"""
Discover where a show is re-uploaded -- BY NAME, without downloading anything.

Give a show name; this searches the whole web + YouTube for that title, its
synonym renames, AND its regional-language translations, scores every hit
against your name (TITLE-LEVEL ONLY -- never the channel name), keeps only
VIDEO links, and lists EXACT matches first, then broader ones.

Coverage:
  - WHOLE WEB via DuckDuckGo (default, keyless) -- any blog/mirror/free site.
  - YouTube via yt-dlp search (keyless).
  - Piracy venues (Moj/ShareChat/Dailymotion/ok.ru/Rumble) probed directly with
    site-scoped queries for the exact title -- this is what catches Moj re-ups.
  - Regional translations (Tamil/Telugu/Kannada/Malayalam/Hindi...) via
    deep-translator, so native-script re-uploads of dubs surface too.
  - Whole web via Google CSE -- OPTIONAL, set GOOGLE_API_KEY + GOOGLE_CSE_ID.

A name match is a LEAD, not proof. Open the URL to eyeball it, or download that
one clip and `scan` it to confirm by content.
"""
from __future__ import annotations

import concurrent.futures
import html
import os
import shutil
import subprocess
import sys
from urllib.parse import urlparse

from . import titlematch

_SEP = "\t"
PLATFORMS = {"youtube": ("ytsearch", "youtube.com")}

# Hosts that serve VIDEO (re-uploads live here). Only links on these hosts -- or
# whose URL clearly points at a video -- are flagged; script/text pages are not.
VIDEO_HOSTS = {
    "youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com",
    "dailymotion.com", "dai.ly", "ok.ru", "odnoklassniki.ru",
    "rumble.com", "vimeo.com", "bilibili.com", "tv.bilibili.com",
    "facebook.com", "fb.watch", "fb.com", "instagram.com",
    "snapchat.com", "sharechat.com", "moj.sharechat.com", "vk.com",
    "bitchute.com", "tiktok.com", "threads.net", "threads.com",
    "joshapp.com", "chingari.io", "x.com", "twitter.com", "kuaishou.com",
    "microtv.sbs", "goodshort.com", "reelshort.com", "netshort.com",
    "flextv.cc", "dramabox.com", "moboreels.com", "youku.com", "iqiyi.com",
}
# Always-drop hosts: scripts / text / encyclopedias / books / non-video.
DENY_HOSTS = {
    "wikipedia.org", "en.wikipedia.org", "m.wikipedia.org", "imdb.com",
    "m.imdb.com", "goodreads.com", "wattpad.com", "pinterest.com",
    "in.pinterest.com", "quora.com", "reddit.com", "medium.com",
    "grokipedia.com", "britannica.com", "fandom.com", "wikia.com",
    "amazon.com", "amazon.in", "flipkart.com", "spotify.com",
    "play.google.com", "apps.apple.com", "linkedin.com", "millionairematch.com",
    "scribd.com", "slideshare.net", "genius.com", "azlyrics.com",
}
# URL shapes that ARE a single video (keep) vs a channel/profile/list (drop).
SINGLE_VIDEO_URL = ("watch?v=", "/watch/", "youtu.be/", "/shorts/", "/video/",
                    "/videos/", "/reel/", "/reels/", "/p/", "/tv/", "/post/",
                    "/embed/", "dai.ly/", "/clip/", "/moment/", "/episode/")
NOT_A_VIDEO_URL = ("/@", "/channel/", "/c/", "/user/", "/profile/", "/playlist",
                   "/tag/", "/tags/", "/hashtag/", "/results", "/search",
                   "/explore", "/about", "/featured", "/community", "/group")
# Piracy venues to probe directly (exact title, site-scoped) for better recall.
PIRACY_SITES = ["moj.sharechat.com", "sharechat.com", "dailymotion.com",
                "ok.ru", "rumble.com"]


def _ytdlp():
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def _host(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:  # noqa: BLE001
        return ""


def _base_host(h: str) -> str:
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def is_single_video(host: str, url: str) -> bool:
    """True only for a link to ONE video on a KNOWN video platform. Drops:
    random/unknown sites (gym reviews, blogs, listings), and channel / profile /
    tag / playlist / search pages even on known hosts. This is the main
    relevance gate -- it keeps the list to actual re-upload videos."""
    if not host:
        return False
    bh = _base_host(host)
    if host in DENY_HOSTS or bh in DENY_HOSTS:
        return False
    # must be a recognised video/streaming/social-video platform
    if host not in VIDEO_HOSTS and bh not in VIDEO_HOSTS:
        return False
    u = (url or "").lower()
    if any(p in u for p in NOT_A_VIDEO_URL):
        return False
    if any(p in u for p in SINGLE_VIDEO_URL):
        return True
    # rumble video pages are rumble.com/v<id>-slug.html ; channels are /c/
    if bh == "rumble.com":
        return u.rstrip("/").endswith(".html") and "/v" in u
    return False


def _tag(rows, q):
    """Stamp each row with the query that produced it (used to also score a
    result against the *translated* query that found it)."""
    for r in rows:
        r["query"] = q
    return rows


def _nonascii(s: str) -> bool:
    """A native-script (translated) query/title -- not a romanized synonym guess."""
    return any(ord(c) > 127 for c in (s or ""))


def _squash(s: str) -> str:
    """Lowercase, strip spaces/punctuation -- so an exclude like 'wowtv' matches
    'WoW TV - Hindi', 'Wow TV', 'Wowtv_Shows' all the same."""
    return "".join(c for c in (s or "").lower() if c.isalnum())


def _is_exact(name: str, found_title: str) -> bool:
    """Exact OR near-exact: typo-tolerant, so 1-2 dropped/swapped letters still
    count as EXACT (e.g. 'Gymwal Billionare' ~ 'Gymwala Billionaire')."""
    return titlematch.near_exact(name, found_title)


def ddg_available() -> bool:
    try:
        import ddgs  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def cse_available() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID"))


def web_available() -> bool:
    return ddg_available() or cse_available()


def query_variants(name: str, max_variants: int = 4, translate: bool = False,
                   langs=None):
    """The name + synonym-swapped variants (+ regional translations if asked)."""
    raw = name.strip()
    toks = titlematch.normalize(name)
    out, seen = [], set()

    def add(s):
        s = s.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)

    add(raw)
    add(" ".join(toks))
    for i, t in enumerate(toks):
        canon = titlematch._canon(t)
        grp = next((g for g in titlematch.SYNONYMS if g[0] == canon), None)
        if not grp:
            continue
        for alt in grp[:3]:
            if alt != t:
                v = toks.copy()
                v[i] = alt
                add(" ".join(v))
            if len(out) > max_variants:
                break
        if len(out) > max_variants:
            break
    base = out[:max_variants + 1]

    if translate:
        from . import translate as _tr
        codes = _tr.to_codes(langs or _tr.DEFAULT_LANGS)
        for t in _tr.translate_title(raw, codes):
            if t.lower() not in seen:
                seen.add(t.lower())
                base.append(t)
    return base


def _search_platform(prefix: str, query: str, limit: int, host: str):
    spec = f"{prefix}{limit}:{query}"
    cmd = _ytdlp() + [
        "--flat-playlist", "--ignore-errors", "--no-warnings",
        "--print", _SEP.join(["%(id)s", "%(title)s", "%(channel,uploader)s",
                              "%(webpage_url,url)s"]),
        spec,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(_SEP)
        if len(parts) < 2 or not parts[1].strip():
            continue
        vid, title = parts[0], parts[1]
        channel = parts[2] if len(parts) > 2 and parts[2] != "NA" else ""
        url = parts[3] if len(parts) > 3 and parts[3] not in ("NA", "") else ""
        if not url and host == "youtube.com" and vid not in ("NA", ""):
            url = f"https://www.youtube.com/watch?v={vid}"
        rows.append({"platform": host, "title": title, "channel": channel,
                     "url": url, "snippet": ""})
    return rows


def _ddg_search(query: str, limit: int, region: str = "in-en"):
    """Keyless whole-web search via DuckDuckGo. Returns [] on any failure."""
    try:
        from ddgs import DDGS
    except Exception:  # noqa: BLE001
        return []
    n = max(1, min(limit, 25))
    hits = None
    for kwargs in ({"region": region, "safesearch": "off", "max_results": n},
                   {"max_results": n}):
        try:
            hits = DDGS().text(query, **kwargs)
            break
        except TypeError:
            continue
        except Exception:  # noqa: BLE001
            return []
    rows = []
    for it in (hits or []):
        url = it.get("href") or it.get("url") or it.get("link") or ""
        host = _host(url)
        rows.append({"platform": host or "web", "title": it.get("title", ""),
                     "channel": host, "url": url, "snippet": it.get("body", "")})
    return rows


def _cse_search(query: str, limit: int):
    if not cse_available():
        return []
    import json
    import urllib.parse
    import urllib.request
    params = urllib.parse.urlencode({
        "key": os.environ["GOOGLE_API_KEY"], "cx": os.environ["GOOGLE_CSE_ID"],
        "q": query, "num": min(10, limit),
    })
    try:
        with urllib.request.urlopen(
                "https://www.googleapis.com/customsearch/v1?" + params, timeout=25) as r:
            data = json.load(r)
    except Exception:  # noqa: BLE001
        return []
    rows = []
    for it in data.get("items", []):
        host = _host(it.get("link", ""))
        rows.append({"platform": host or "web", "title": it.get("title", ""),
                     "channel": host, "url": it.get("link", ""),
                     "snippet": it.get("snippet", "")})
    return rows


def discover(name: str, limit: int = 20, threshold: float = 50.0,
             platforms=("youtube",), use_web: bool = True, exclude=(),
             throttle: float = 1.0, video_only: bool = True,
             translate: bool = True, langs=None, sites: bool = True,
             workers: int = 8):
    """Search the web + YouTube for `name` (+ synonym & translation variants);
    return scored, video-only leads with EXACT matches first.

    Matching is on the found page/video TITLE only -- never the channel name, so
    a channel merely *named* like your show is not flagged on that basis.
    """
    variants = query_variants(name, translate=translate, langs=langs)
    excl = [_squash(e) for e in exclude if e.strip()]
    raw = []

    # Build every search call, then run them all IN PARALLEL (network-bound, so
    # this is ~5-10x faster than one-at-a-time).
    web = use_web and web_available()
    tasks = []
    for q in variants:
        for p in platforms:
            if p in PLATFORMS:
                prefix, host = PLATFORMS[p]
                tasks.append((lambda q, pr, h: _tag(_search_platform(pr, q, limit, h), q),
                              (q, prefix, host)))
        if web:
            tasks.append((lambda q: _tag(_ddg_search(q, limit), q), (q,)))
            if cse_available():
                tasks.append((lambda q: _tag(_cse_search(q, limit), q), (q,)))
    if web and sites:
        for s in PIRACY_SITES:
            tasks.append((lambda s: _tag(_ddg_search(f'{name} site:{s}', limit), name), (s,)))

    raw = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(fn, *a) for fn, a in tasks]
        for fu in concurrent.futures.as_completed(futs):
            try:
                raw += fu.result()
            except Exception:  # noqa: BLE001
                pass

    best = {}
    for r in raw:
        # owner-exclusion: hide YOUR OWN channels/uploads. Checks channel, url AND
        # title (space/punctuation-insensitive) -- so "wowtv" hides "WoW TV - Hindi",
        # "Wowtv_Shows", and titles that carry the WoW TV credit. Matching never
        # uses these fields.
        if excl:
            squashed = [_squash(r.get(k, "")) for k in ("channel", "url", "title")]
            if any(e in sq for e in excl for sq in squashed):
                continue
        if video_only and not is_single_video(r.get("platform", ""), r.get("url", "")):
            continue
        title = r["title"]
        q = r.get("query") or name
        s = titlematch.score(name, title)           # vs YOUR real title (TITLE only)
        score_val = s["score"]
        exact = _is_exact(name, title)
        # A NATIVE-SCRIPT (translated) query that NEAR-exactly matches the found
        # title is a real dub re-upload -> promote it. Restricted to native-script
        # + near-exact so neither a romanized synonym guess nor a generic
        # cross-language word coincidence can inflate the score.
        if q != name and _nonascii(q) and _is_exact(q, title):
            exact = True
            score_val = max(score_val, 100.0)
        if score_val < threshold:
            continue
        key = r["url"] or (title + "|" + r.get("channel", ""))
        rec = {**r, "score": score_val, "shared": s["shared_concepts"], "exact": exact}
        if key not in best or rec["score"] > best[key]["score"]:
            best[key] = rec
    # EXACT matches first, then by score
    results = sorted(best.values(), key=lambda x: (not x["exact"], -x["score"]))
    return {"name": name, "variants": variants, "results": results,
            "web_used": use_web and web_available(),
            "web_backends": _backends_label(use_web),
            "video_only": video_only, "translated": translate}


def _backends_label(use_web: bool) -> str:
    if not use_web:
        return "web OFF"
    bk = []
    if ddg_available():
        bk.append("DuckDuckGo")
    if cse_available():
        bk.append("Google CSE")
    return " + ".join(bk) if bk else "web unavailable (pip install ddgs)"


# ---- HTML report (clickable) --------------------------------------------
def _score_color(s: float) -> str:
    if s >= 85:
        return "#b91c1c"
    if s >= 65:
        return "#c2410c"
    return "#a16207"


def render_html(reports, threshold: float, exclude=()) -> str:
    esc = html.escape
    total = sum(len(r["results"]) for r in reports)
    rows_html = []
    for rep in reports:
        nm = esc(rep["name"])
        res = rep["results"]
        if not res:
            rows_html.append(
                f'<tr class="grp"><td colspan="4"><b>{nm}</b> '
                f'<span class="muted">- no video leads above {threshold:g}</span></td></tr>')
            continue
        rows_html.append(
            f'<tr class="grp"><td colspan="4"><b>{nm}</b> '
            f'<span class="muted">- {len(res)} video lead(s)</span></td></tr>')
        for r in res:
            color = _score_color(r["score"])
            exact = '<span class="ex">EXACT</span> ' if r.get("exact") else ""
            concept = (" · ".join(esc(c) for c in r["shared"])) if r["shared"] else ""
            link = (f'<a href="{esc(r["url"])}" target="_blank" rel="noopener">'
                    f'{esc(r["url"])}</a>') if r.get("url") else '<span class="muted">(no url)</span>'
            snip = esc((r.get("snippet") or "")[:160])
            rows_html.append(
                '<tr>'
                f'<td class="score" style="color:{color}">{exact}{r["score"]:.0f}</td>'
                f'<td><span class="host">{esc(r["platform"])}</span>'
                f'{("<br><span class=muted>" + esc(r["channel"]) + "</span>") if r.get("channel") else ""}</td>'
                f'<td><div class="title">{esc(r["title"])}</div>'
                f'{("<div class=concept>" + concept + "</div>") if concept else ""}'
                f'{("<div class=snip>" + snip + "</div>") if snip else ""}</td>'
                f'<td class="urlcell">{link}</td>'
                '</tr>')
    excl_note = (f' · hiding: {esc(", ".join(exclude))}' if exclude else "")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ContentGuard - video leads</title>
<style>
 body{{font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#1f2937;background:#f8fafc}}
 header{{background:#0f172a;color:#fff;padding:18px 22px}}
 header h1{{margin:0;font-size:20px}} header p{{margin:6px 0 0;color:#cbd5e1;font-size:13px}}
 .wrap{{padding:18px 22px}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08);border-radius:8px;overflow:hidden}}
 th,td{{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #eef2f7}}
 th{{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}}
 tr.grp td{{background:#f8fafc;border-top:2px solid #e2e8f0}}
 .score{{font-weight:700;font-size:16px;text-align:center;width:62px}}
 .ex{{display:block;font-size:10px;font-weight:800;color:#fff;background:#b91c1c;border-radius:8px;padding:0 4px}}
 .host{{font-weight:600}} .muted{{color:#94a3b8;font-size:12px}}
 .title{{font-weight:500}} .concept{{color:#0369a1;font-size:12px;margin-top:2px}}
 .snip{{color:#64748b;font-size:12px;margin-top:3px}}
 .urlcell{{max-width:340px;word-break:break-all;font-size:12px}}
 a{{color:#2563eb}} footer{{padding:14px 22px;color:#94a3b8;font-size:12px}}
</style>
<header>
 <h1>WOW TV - video re-upload leads</h1>
 <p>{len(reports)} show(s) · {total} video lead(s) · score ≥ {threshold:g}{excl_note}
 · EXACT matches first · backend: {esc(reports[0]["web_backends"]) if reports else "-"}</p>
</header>
<div class="wrap">
 <table>
  <tr><th>Score</th><th>Where</th><th>Found title</th><th>Link</th></tr>
  {''.join(rows_html)}
 </table>
 <footer>Video links only (script/text pages filtered out). A title match is a
 <b>LEAD, not proof</b> - open each link, then confirm a clip with
 <code>python -m contentguard scan &lt;url&gt;</code>.</footer>
</div>
</html>"""
