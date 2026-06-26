"""
Title intelligence -- catch rivals who RENAME a stolen show to a synonym.

Pirates don't just re-encode the video, they rename the title:
  "Billionaire Boyfriend"      -> "Rich Boyfriend"
  "The CEO's Secret Wife"      -> "Boss's Hidden Bride"
  "Contract Marriage"          -> "Fake Wedding Deal"

Exact-title search misses all of these. This module scores any rival title
against your catalog titles using TWO signals:
  1. SYNONYM-canonical token overlap -- "billionaire"=="rich"=="ceo", so the
     trope words collapse to one key and synonym renames still match.
  2. Fuzzy string similarity (stdlib difflib) -- catches typos, word reorder,
     episode/season noise, transliteration spacing.

IMPORTANT: a title match is a LEAD, not proof. Anyone can name a show "Rich
Boyfriend". Use this to build a shortlist, then CONFIRM each lead with the
fingerprint engine (`scan`) -- the audio/video match is the actual evidence.

Pure Python stdlib -- no extra installs.
"""
from __future__ import annotations

import csv
import difflib
import re

# Recurring micro-drama vocabulary. Each list collapses to its first word (the
# canonical key), so any two synonyms compare as equal. Extend freely.
SYNONYMS = [
    ["rich", "wealthy", "billionaire", "trillionaire", "millionaire", "tycoon",
     "ceo", "boss", "mogul", "magnate", "heir", "heiress", "elite", "luxury",
     "ameer", "dolatmand", "crorepati"],
    ["poor", "broke", "penniless", "cinderella", "maid", "servant", "nanny",
     "waitress", "gareeb", "naukrani"],
    ["boyfriend", "lover", "beau", "sweetheart", "boy", "prince", "premi",
     "aashiq"],
    ["girlfriend", "lady", "girl", "princess", "premika"],
    ["husband", "hubby", "groom", "pati", "shauhar"],
    ["wife", "bride", "spouse", "missus", "patni", "dulhan", "biwi", "begum"],
    ["fiance", "fiancee", "betrothed", "mangetar"],
    ["ex", "former", "exwife", "exhusband"],
    ["secret", "hidden", "undercover", "disguised", "incognito", "masked",
     "concealed", "chupa", "chupi", "raaz", "gupt"],
    ["revenge", "vengeance", "payback", "retribution", "badla", "intequam"],
    ["love", "romance", "affair", "passion", "pyaar", "ishq", "mohabbat",
     "prem"],
    ["marriage", "wedding", "married", "nuptials", "shaadi", "vivah", "byah"],
    ["contract", "fake", "pretend", "arranged", "deal", "agreement", "naqli"],
    ["baby", "child", "son", "daughter", "kid", "heir", "bachcha", "beta",
     "beti"],
    ["alpha", "dominant", "fierce", "ruthless", "savage"],
    ["mafia", "gangster", "don", "underworld", "mob", "bhai"],
    ["divorce", "separation", "split", "talaq"],
    ["substitute", "replacement", "stand-in", "double", "fake", "duplicate"],
    ["doctor", "surgeon", "physician", "dr"],
    ["king", "emperor", "lord", "master", "raja", "badshah"],
    ["queen", "empress", "rani", "malika"],
    ["return", "comeback", "rebirth", "reborn", "regression", "wapsi"],
    ["enemy", "rival", "foe", "nemesis", "dushman"],
    ["forbidden", "taboo", "illicit", "forbidden"],
]

# stopwords + episode/quality noise stripped before matching
# NOTE: "wala/wali/wale" are NOT stopwords -- they are part of distinctive WOW TV
# titles (Gymwala, Chaiwala, Kachrewala, London Wale) and dropping them breaks
# matching when a pirate splits "Gymwala" into "Gym Wala".
_STOP = {"the", "a", "an", "of", "and", "&", "to", "my", "his", "her", "their",
         "is", "in", "on", "with", "for", "me", "you", "ka", "ki", "ke", "ko",
         "se", "hai", "ho", "na"}
_NOISE = {"ep", "episode", "epi", "part", "pt", "season", "vol", "volume",
          "full", "hd", "4k", "official", "trailer", "promo", "teaser", "clip",
          "shorts", "short", "reel", "video", "movie", "series", "webseries",
          "hindi", "english", "subtitle", "subtitles", "dubbed", "new", "latest",
          "viral", "trending"}

# build token -> canonical lookup
_LUT = {}
for grp in SYNONYMS:
    key = grp[0]
    for w in grp:
        _LUT[w] = key


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _canon(tok: str) -> str:
    if tok in _LUT:
        return _LUT[tok]
    s = _stem(tok)
    return _LUT.get(s, s)


def normalize(title: str):
    """Return cleaned, lowercased raw tokens (episode/quality noise removed)."""
    t = title.lower()
    t = re.sub(r"[‘’“”']", "", t)       # quotes
    t = re.sub(r"s\d+\s*e\d+|s\d+|e\d+|ep\.?\s*\d+", " ", t)  # s01e05 / ep 5
    # keep letters of ALL scripts (Hindi/Tamil/Telugu/...) so translated titles
    # actually match; only punctuation/emoji are dropped.
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = t.replace("_", " ")
    toks = [w for w in t.split() if w and not w.isdigit()]
    toks = [w for w in toks if w not in _STOP and w not in _NOISE]
    return toks


def canon_set(title: str):
    return {_canon(w) for w in normalize(title)}


try:                                   # rapidfuzz: faster + better Unicode fuzzy
    from rapidfuzz import fuzz as _rf

    def _ratio(a: str, b: str) -> float:        # 0..1 whole-string similarity
        return _rf.ratio(a, b) / 100.0

    def _partial(a: str, b: str) -> float:      # 0..100 best substring of b ~ a
        return _rf.partial_ratio(a, b)

    def _token_set(a: str, b: str) -> float:    # 0..100 order/extra-word tolerant
        return _rf.token_set_ratio(a, b)
except Exception:                      # noqa: BLE001  (stdlib fallback)
    def _ratio(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    def _partial(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if len(a) >= len(b):
            return _ratio(a, b) * 100
        best = 0.0
        for i in range(len(b) - len(a) + 1):
            best = max(best, _ratio(a, b[i:i + len(a)]))
        return best * 100

    def _token_set(a: str, b: str) -> float:
        return _ratio(" ".join(sorted(a.split())),
                      " ".join(sorted(b.split()))) * 100


def _tok_close(a: str, b: str) -> bool:
    """Two word-tokens are 'the same word' despite a 1-2 letter typo/drop
    (e.g. doctr~doctor, billionare~billionaire, gymwal~gymwala)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 3:
        return False
    return _ratio(a, b) >= 0.80


def _is_trope(tok: str) -> bool:
    """A common micro-drama vocabulary word (billionaire/boss/wife/love/...).
    It appears in tons of titles, so on its OWN it is not evidence of a copy."""
    return tok in _LUT or _stem(tok) in _LUT


def _weight(tok: str) -> float:
    """Distinctive words (bhikhari, gymwala, banarasiya) carry the match;
    generic trope words barely count."""
    return 0.35 if _is_trope(tok) else 1.0


def _match_tok(ta: str, tb: str) -> bool:
    """Same word (typo-tolerant) OR same trope concept (billionaire==rich)."""
    return _tok_close(ta, tb) or _canon(ta) == _canon(tb)


def _fuzzy_overlap(a_raw, b_raw) -> int:
    """How many tokens of a_raw have a distinct typo-close match in b_raw."""
    pool = list(b_raw)
    matched = 0
    for ta in a_raw:
        for j, tb in enumerate(pool):
            if _tok_close(ta, tb):
                pool.pop(j)
                matched += 1
                break
    return matched


def near_exact(title_a: str, title_b: str) -> bool:
    """True if title_b is title_a with only tiny spelling drops/swaps: every
    word of yours appears (typo-tolerant), with at most one extra word.
    Catches 'Doctr Princess' ~ 'Doctor Princess', 'Gymwal Billionare' ~
    'Gymwala Billionaire'."""
    a, b = normalize(title_a), normalize(title_b)
    if len(a) < 1 or not b:
        return False
    if _fuzzy_overlap(a, b) == len(a) and (len(b) - len(a)) <= 1:
        return True
    # space-insensitive: 'Gym Wala' == 'Gymwala', 'Bill ionaire' == 'Billionaire'
    ja, jb = "".join(a), "".join(b)
    if ja and jb and abs(len(ja) - len(jb)) <= 3:
        return difflib.SequenceMatcher(None, ja, jb).ratio() >= 0.90
    return False


def _distinct_present(distinct, b_raw, core, b_join) -> bool:
    """Is the show's distinctive core actually in the candidate? Spacing- and
    typo-tolerant for cores >=4 chars (despaced substring/fuzzy), exact-ish for
    very short distinctive words."""
    if not distinct:
        return True                          # nothing distinctive to gate on
    # candidate must be long enough to actually CONTAIN the core (not be a mere
    # fragment of it, e.g. "Gym" is not "Gymwala")
    if len(core) >= 4 and len(b_join) >= 0.6 * len(core) and _partial(core, b_join) >= 82:
        return True
    return any(any(_tok_close(d, x) for x in b_raw) for d in distinct)


def score(title_a: str, title_b: str) -> dict:
    """0..100 similarity. `title_a` is YOUR show. Tuned for micro-drama
    re-upload hunting:

    - A shared *distinctive* word (bhikhari, gymwala, banarasiya) is what counts;
      a shared *trope* word (boss/billionaire/love) barely does -- so "Bigg Boss"
      does NOT match "Bhikhari Boss".
    - Robust to SPACING ("Gym Wala" == "Gymwala") and TYPOS ("Gym Bala",
      "billionare") via despaced substring + fuzzy -- so a real re-upload titled
      "GYM WALA BILLIONAIRE FULL EPISODE" is NOT missed.
    - Renames map through synonyms ("Rich Boyfriend" ~ "Billionaire Boyfriend").
    """
    a, b = normalize(title_a), normalize(title_b)
    if not a or not b:
        return {"score": 0.0, "synonym_overlap": 0.0, "fuzzy": 0.0,
                "shared_concepts": []}

    if near_exact(title_a, title_b):
        sh = [t for t in a if not _is_trope(t)]
        return {"score": 100.0, "synonym_overlap": 100.0, "fuzzy": 100.0,
                "shared_concepts": sorted(set(sh)) or sorted(set(a) & set(b))}

    distinct = [t for t in a if not _is_trope(t)]
    b_join = "".join(b)
    core = "".join(distinct) if distinct else "".join(a)

    core_sim = (_partial(core, b_join)
                if (len(core) >= 4 and len(b_join) >= 0.6 * len(core)) else 0.0)
    # rename/order/extra-word tolerant similarity on the canonical (synonym) form
    full_sim = _token_set(" ".join(_canon(t) for t in a),
                          " ".join(_canon(t) for t in b))

    if not _distinct_present(distinct, b, core, b_join):
        final = 0.35 * full_sim              # distinctive core absent -> weak lead
    elif distinct:
        final = max(full_sim, 0.5 * core_sim + 0.5 * full_sim)
    else:
        final = full_sim                     # all-trope title -> pure rename/fuzzy

    shared = sorted({(_canon(t) if _is_trope(t) else t)
                     for t in a if any(_match_tok(t, x) for x in b)})
    return {"score": round(min(final, 100.0), 1),
            "synonym_overlap": round(full_sim, 1),
            "fuzzy": round(core_sim, 1),
            "shared_concepts": shared}


def best_matches(rival_titles, catalog_titles, threshold: float = 55.0):
    """For each rival title, find its best catalog match above threshold.

    rival_titles / catalog_titles: lists of strings (or (title, meta) tuples;
    only the string is used). Returns ranked list of suspicious pairs.
    """
    cat = [t if isinstance(t, str) else t[0] for t in catalog_titles]
    out = []
    for rt in rival_titles:
        if isinstance(rt, str):
            rstr, rsrc = rt, None
        else:
            rstr, rsrc = rt[0], (rt[1] if len(rt) > 1 else None)
        best, best_s = None, None
        for ct in cat:
            s = score(rstr, ct)
            if best_s is None or s["score"] > best_s["score"]:
                best_s, best = s, ct
        if best_s and best_s["score"] >= threshold:
            rec = {"rival_title": rstr, "matched_catalog_title": best, **best_s}
            if rsrc:
                rec["rival_source"] = rsrc
            out.append(rec)
    out.sort(key=lambda r: -r["score"])
    return out


# ---- loading rival/your title lists -------------------------------------
def load_titles(source: str):
    """Load titles from a .txt (one per line), .csv (a 'title' column or first
    column), or a playlist/channel URL (via yt-dlp --flat-playlist)."""
    from . import media
    if media.is_url(source):
        return media.list_titles(source)

    low = source.lower()
    if low.endswith(".csv"):
        rows = []
        with open(source, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            ti = 0
            if header:
                lh = [h.strip().lower() for h in header]
                ti = lh.index("title") if "title" in lh else 0
                if "title" not in lh and header:
                    rows.append(header[ti])  # header wasn't a header
            for r in reader:
                if r and len(r) > ti:
                    rows.append(r[ti].strip())
        return [t for t in rows if t]

    with open(source, encoding="utf-8-sig") as f:
        return [ln.strip() for ln in f if ln.strip()]
