"""
Regional-language title translation -- so we can hunt re-uploads that pirates
post under a NATIVE-SCRIPT title (Tamil / Telugu / Kannada / Malayalam / ...).

WOW TV dubs a show into many languages; a pirate re-uploading the Tamil dub
usually titles it in Tamil script, which an English/Hindi-only search never
finds. This translates a title into the catalog's languages so `discover` can
search those names too.

Uses deep-translator (free, NO API key) if installed; degrades to [] otherwise
(install with: pip install deep-translator). Runs locally on your machine.
"""
from __future__ import annotations

import time

# catalog language name -> Google Translate code
LANG_CODES = {
    "hindi": "hi", "tamil": "ta", "telugu": "te", "kannada": "kn",
    "malayalam": "ml", "bengali": "bn", "marathi": "mr", "gujarati": "gu",
    "punjabi": "pa", "english": "en", "haryanvi": "hi",
}
# sensible default targets (the big dubbing languages)
DEFAULT_LANGS = ["hi", "ta", "te", "kn", "ml"]

_cache = {}


def available() -> bool:
    try:
        import deep_translator  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def to_codes(langs):
    """Map names/codes to dedup'd translate codes."""
    seen, out = set(), []
    for l in (langs or []):
        c = LANG_CODES.get(l.strip().lower(), l.strip().lower())
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def translate_title(title, lang_codes, throttle: float = 0.4):
    """Return native-script translations of `title` into each target language.

    Cached and throttled. Never raises -- returns [] on any failure so a scan
    keeps going if translation is unavailable or rate-limited.
    """
    if not available() or not title.strip():
        return []
    from deep_translator import GoogleTranslator
    out = []
    for code in lang_codes:
        key = (title.strip().lower(), code)
        if key in _cache:
            t = _cache[key]
        else:
            try:
                t = GoogleTranslator(source="auto", target=code).translate(title)
            except Exception:  # noqa: BLE001
                t = None
            _cache[key] = t
            if throttle:
                time.sleep(throttle)
        if t and t.strip() and t.strip().lower() != title.strip().lower():
            out.append(t.strip())
    # dedup, keep order
    seen, res = set(), []
    for t in out:
        if t.lower() not in seen:
            seen.add(t.lower())
            res.append(t)
    return res
