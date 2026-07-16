"""
Identify suspect links you already have (e.g. Facebook /share/ links passed
around on WhatsApp). Search engines cannot FIND these - the URL is an opaque id
with no title, and the /share/ form is not indexed - but once you HAVE a link,
this opens it, reads the caption/title from its link-preview metadata (which even
Facebook serves to preview crawlers), and matches it against your WOW TV catalog
to tell you which show it is.
"""
from __future__ import annotations

import concurrent.futures
import html as _html
import re
import urllib.error
import urllib.request

from . import titlematch

# Sites serve Open Graph preview metadata to link-preview crawlers even without
# login. Facebook rejects a normal browser UA (400) but answers this one.
_CRAWLER_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"

_DEAD = ("isn't available anymore", "no longer available", "content isn't available",
         "this content isn't available", "this page isn't available",
         "video unavailable", "video no longer exists", "content not found")


def _meta(page: str, prop: str) -> str:
    for pat in (r'<meta[^>]+property=["\']' + prop + r'["\'][^>]+content=["\']([^"\']*)',
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']' + prop):
        m = re.search(pat, page, re.I)
        if m and m.group(1).strip():
            return _html.unescape(m.group(1)).strip()
    return ""


def fetch_meta(url: str, timeout: int = 15) -> dict:
    """Fetch a URL's link-preview metadata. Returns title, description, combined
    text, and live=False only when confidently removed."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _CRAWLER_UA, "Accept-Language": "en-US,en;q=0.9"})
        page = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"title": "", "description": "", "text": "",
                "live": e.code not in (404, 410), "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"title": "", "description": "", "text": "", "live": True, "error": str(e)[:60]}
    title = _meta(page, "og:title") or _meta(page, "twitter:title")
    desc = _meta(page, "og:description") or _meta(page, "twitter:description")
    # uploader / page name (the real signal: one account posting many reels)
    uploader = ""
    mu = re.search(r"(?:reel|video|post) by ([^|»·\n<]+)",
                   title + " | " + _meta(page, "twitter:title"), re.I)
    if mu:
        uploader = mu.group(1).strip(" -|·")[:60]
    live = not any(d in page.lower() for d in _DEAD)
    return {"title": title, "description": desc, "uploader": uploader,
            "text": f"{title} {desc}".strip(), "live": live, "error": ""}


def check_urls(urls, catalog, threshold: float = 55.0, workers: int = 8,
               drop_dead: bool = True):
    """For each URL, read its caption and match it against your catalog titles.

    Returns list of dicts: url, caption, matched_show, score, live, error.
    `catalog` = list of your show titles (strings).
    """
    cat = [t if isinstance(t, str) else t[0] for t in catalog]

    def _one(url):
        m = fetch_meta(url)
        # strip hashtags, @mentions and urls before matching -- "#Drama #hindi"
        # must not match a show titled "... Drama ..."
        text = re.sub(r"[#@]\w+", " ", m["text"])
        text = re.sub(r"https?://\S+", " ", text)
        best, best_s = "", 0.0
        if text.strip():
            for ct in cat:
                sc = titlematch.score(ct, text)["score"]
                if sc > best_s:
                    best_s, best = sc, ct
        # Only claim a match when a DISTINCTIVE (non-trope) show word actually
        # appears in the caption, or it is near-exact. A shared trope word alone
        # ("pati", "shaadi") is NOT enough -- that was giving false matches.
        cap_toks = titlematch.normalize(text)
        distinct_hit = best and any(
            (not titlematch._is_trope(w)) and any(titlematch._tok_close(w, x) for x in cap_toks)
            for w in titlematch.normalize(best))
        confident = bool(best) and (best_s >= 85 or (best_s >= threshold and distinct_hit))
        return {"url": url, "caption": (m["description"] or m["title"])[:160],
                "uploader": m.get("uploader", ""),
                "matched_show": best if confident else "",
                "score": round(best_s, 1),
                "live": m["live"], "error": m.get("error", "")}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        out = list(ex.map(_one, urls))
    if drop_dead:
        out = [r for r in out if r["live"]]
    return out
