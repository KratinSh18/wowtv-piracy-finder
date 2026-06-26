# ContentGuard 🛡️

A self-hosted **"Content ID" for micro-dramas.** Catch your WOW TV dramas when
**any** rival app or site re-uploads them — even after they crop, re-encode, slap
their logo on, change the resolution, mirror it, speed it up, rename the title,
or use only a clip. Built to monitor **many platforms at once**, not one.

It does this with three independent layers:

| Layer | What it catches | Survives |
|---|---|---|
| 🎧 **Audio fingerprinting** (Shazam-style landmarks) | Pirates reuse your original audio track (dialogue + score) almost every time | MP3/AAC re-encode, volume change, noise, partial clips |
| 🎬 **Video fingerprinting** (perceptual hashing) | The visuals, when audio is muted/replaced | re-encode, resize, crop, letterbox, small logo overlay, brightness/contrast |
| 🔏 **Invisible watermark** (forensic, *proactive*) | Embed *before* release → later **prove it's yours** & trace which partner leaked | JPEG/H.264 re-encode, resize |

> **It already works (verified on real video).** Four pirate versions of one
> clip — (1) cut to 10s + downscaled 640×360→480×270 + logo box + heavy
> re-encode, (2) **horizontally mirrored**, (3) **sped up to 1.05×**, (4) an
> unrelated clip — were all judged correctly: the three rips → **MATCH at 100%
> confidence** (with the exact stolen offset reported), the unrelated clip →
> **NO MATCH** (no false positive). Mirror and speed-change are the two evasions
> that defeat naive matchers; both are handled.

---

## Install

```bash
pip install -r requirements.txt          # numpy, scipy, Pillow
# ffmpeg + ffprobe must be on PATH for real media (NOT needed for selftest):
#   Windows: winget install Gyan.FFmpeg
# optional, to fetch suspect clips from URLs:
pip install yt-dlp
```

## Prove it works (no content or ffmpeg needed)

```bash
python -m contentguard selftest
```
Synthesises audio/video, applies pirate-style mangling (noise, zoom, logo,
re-encode, mirror, 1.05× speed), and confirms every layer still matches:
```
[PASS] audio: matched work=1 votes=33 offset=10.03s (expected ~10.0s)
[PASS] audio speed: 1.05x rip gave 6 votes uncorrected -> 697 votes after speed search
[PASS] video: normal 12/24 (50%), MIRRORED 12/24 (50%) matched after zoom+logo+noise
[PASS] watermark: recovered id=0x0BADF00D after JPEG q80 | PSNR=40.6dB
```

## Two ways to use it

**Mode A — by NAME (no download).** Best when the catalog is huge (Kuku Studio
has every show) and you can't fingerprint each file. Give a show name; it
searches **the whole web** for that title *and its synonym renames* and tells
you which site/channel has it. Fast, scalable, files not needed. **Keyless** —
the web sweep uses DuckDuckGo out of the box (`pip install ddgs`), no API setup.

**Mode B — by CONTENT (fingerprint).** When you have the actual file (or a
suspect clip), `scan` proves it's the same video even after re-encode/crop/logo/
mirror/speed — the strongest evidence.

Typical flow: **`discover` to find leads by name → eyeball the link → (optional)
`scan` one clip to confirm by content.**

```bash
# ---- Mode A: find by NAME (your main flow) -------------------------------
python -m contentguard discover "Billionaire Boyfriend" --exclude "wow tv,wowtv,kuku"
python -m contentguard discover shows.csv --exclude "wow tv,wowtv,kuku" --report leads.html
#   Searches the WHOLE WEB free via DuckDuckGo (no key) + YouTube via yt-dlp.
#   For extra recall, also set GOOGLE_API_KEY + GOOGLE_CSE_ID (Google
#   Programmable Search) -- it runs alongside DuckDuckGo when present.
#   --exclude hides YOUR OWN channels so only third-party uploads remain.
#   --report writes a clickable HTML page of every lead (open in a browser).
#   shows.csv = your Live Show Tracker exported as CSV (a 'title' column).

# ---- Mode B: confirm by CONTENT ------------------------------------------
python -m contentguard ingest /path/to/that/one/show.mp4    # the show you're chasing
python -m contentguard scan https://any-site.com/video/123  --save --evidence case.json
python -m contentguard scan watchlist.txt  --save           # many suspect URLs/files at once

# ---- supporting commands -------------------------------------------------
python -m contentguard titlescan rivalA.txt "https://rivalB.com/channel/x" --mine mine.txt
python -m contentguard cases                  # review all leads/matches, any platform
python -m contentguard cases --export cases.csv
python -m contentguard works ; python -m contentguard rm 7
python -m contentguard wm-embed master.mp4 out.mp4 --id 1001 --video   # optional watermark
```

`discover` prints, per show name, the likely re-uploads (platform, channel, URL,
title, similarity, shared trope-words) — open the link to verify. A name match
is a strong **lead**, not court proof; `scan` is the content proof. A `scan`
verdict (`MATCH`/`LIKELY`/`NO MATCH`) includes the platform, aligned offset, and
with `--evidence` a JSON record incl. the suspect's **SHA-256** for takedowns.

---

## How the matching works

1. **Audio** → STFT spectrogram → pick spectral peaks (a sparse *constellation*)
   → hash peak pairs `(f1, f2, Δt)`. A real match produces *many* hashes that
   line up at a **single consistent time offset** (`ref_time − query_time`); the
   height of that offset's histogram bin is the score. This is the algorithm
   Shazam uses, and it's why a logo/crop/re-encode can't hide a stolen clip —
   the audio landmarks are untouched.
2. **Video** → sample frames (1 fps) → 64-bit DCT perceptual hash per frame →
   count the fraction of suspect frames within a small Hamming distance of any
   reference frame. Used to *confirm* the audio hit and to catch muted re-uploads.
3. **Confidence** = `0.7·audio + 0.3·video` (audio is the trustworthy primary),
   with a bonus when both agree. Thresholds live in `contentguard/config.py` —
   re-tune them once your real catalog is loaded.

---

## Scaling to a real anti-piracy operation

The CLI is the detection engine. The full pipeline a content team runs:

```
        ┌─ your masters ─┐
        │ ingest + watermark
        ▼
   [ Reference DB ]  ◄──────────────┐
        ▲                           │ match
        │                     [ Matching engine ]
   crawl rivals                     ▲
   (Moj/ShareChat share pages,      │ fingerprint
    search by title, new uploads) ──┘
        │
        ▼
   suspect clips ──► MATCH? ──► evidence.json ──► takedown
```

- **Crawling**: `scan <url>` already pulls a clip via `yt-dlp`. To monitor at
  scale, schedule a watcher that lists a rival's new uploads (public share pages
  / search by your drama titles) and feeds URLs into `scan`. ⚠️ Respect each
  platform's Terms of Service and India's IT Act before automated crawling —
  prefer official APIs / public share links, throttle, and keep logs.
- **Storage**: SQLite is fine to tens of millions of audio hashes. Beyond that,
  move the audio-hash index to PostgreSQL or a key-value store, and put video
  hashes in a vector/BK-tree index.

## Evasion coverage (where this stands)

**Handled now** (verified):

| Pirate trick | How it's beaten |
|---|---|
| Re-encode / resolution / bitrate churn | audio landmarks + pHash both survive |
| Crop / zoom (small), letterbox, logo overlay (small) | pHash tolerates it; audio untouched |
| Brightness / contrast / colour shift | pHash thresholds against the AC median (brightness-invariant) |
| **Linear speed change (e.g. 1.05×)** | multi-speed audio search (`SPEED_GRID`) re-aligns the landmarks |
| **Mirror / horizontal flip** | reference stores both orientations (`FLIP_INVARIANT`) |
| Clip stitched into a longer compilation | audio votes are absolute (not a fraction); video is containment-aware (`MIN_VIDEO_FRAMES`) |
| Replace / mute audio | video layer carries it |

**Roadmap / known gaps** (audio is the trustworthy primary while these are open):

| Pirate trick | Beats | Mitigation to add |
|---|---|---|
| **Pitch shift** (not just speed) | audio hash (frequency bins move) | constant-Q / Panako-style log-frequency fingerprint as a 2nd matcher |
| **Heavy zoom / full-frame overlay / aspect re-frame** | video pHash | deep copy-detection embeddings (SSCD / VSC) + FAISS re-rank |
| **AI re-render / interpolation / upscaling** | video pHash + classic watermark | learned video descriptors; audio still wins if reused |
| **Re-record off a screen (camera/analog hole)** | both + watermark grid | neural watermark (VideoSeal/AudioSeal) + capture-augmented embeddings |
| **Fully re-voiced (TTS/dub) or music-swapped** | audio entirely | only a strong video matcher catches it |

## Title intelligence — catch RENAMED shows 🎯

Pirates rename a stolen show to a synonym so exact-title search misses it:
`Billionaire Boyfriend` → `Rich Boyfriend`, `The CEO's Secret Wife` →
`Boss's Hidden Bride`, even Hindi: `Revenge of the Maid` → `Naukrani ka Badla`.

`titlescan` flags these by collapsing trope words to a canonical key
(billionaire = rich = CEO = boss) plus fuzzy matching — **English + Hindi/Hinglish**:

```bash
# rival titles from a text file (one per line), CSV (title column), OR a
# channel/playlist URL (yt-dlp lists titles without downloading):
python -m contentguard titlescan rival_titles.txt          # vs your ingested catalog
python -m contentguard titlescan rival_titles.txt --mine my_titles.txt
python -m contentguard titlescan "https://rival.app/channel/xyz"  --threshold 55
```

Example output (all real renames flagged, unrelated titles ignored):
```
100.0  "Rich Boyfriend Episode 1"  ~= your "Billionaire Boyfriend"   via [boyfriend, rich]
100.0  "Naukrani ka Badla"         ~= your "Revenge of the Maid"     via [poor, revenge]
 80.0  "Fake Wedding Deal"         ~= your "Contract Marriage"        via [contract, marriage]
```

⚠️ A title match is a **lead, not proof** — anyone can name a show "Rich
Boyfriend". Use it to build a shortlist, then **download each flagged clip and
`scan` it** so the audio/video fingerprint is the actual evidence. Add your own
trope synonyms (incl. regional languages) to `SYNONYMS` in `titlematch.py`.

## Production upgrade path (when the cheap baseline saturates)

The MVP is intentionally pure-numpy/scipy/Pillow (commodity hardware, MIT/BSD
deps). Drop-in upgrades, in priority order:

- **Audio, pitch-robust** → [Panako 2.0](https://github.com/JorenSix/Panako)
  (constant-Q, AGPL) as a second matcher. Reference design we already follow:
  [Dejavu](https://github.com/worldveil/dejavu) (MIT),
  [audfprint](https://github.com/dpwe/audfprint) (MIT).
- **Video, crop/overlay/AI-render robust** → deep copy-detection embeddings:
  [SSCD](https://github.com/facebookresearch/sscd-copy-detection),
  [ISC2021 winner](https://github.com/lyakaap/ISC21-Descriptor-Track-1st) (MIT),
  [VSC2022 winner](https://github.com/FeipengMa6/VSC22-Submission) (timestamp
  localization), indexed with [FAISS](https://github.com/facebookresearch/faiss).
  Cheap recall first: Meta [PDQ + TMK](https://github.com/facebook/ThreatExchange) (BSD).
- **Watermark, screen-capture robust** → Meta
  [VideoSeal + AudioSeal](https://github.com/facebookresearch/videoseal) (MIT,
  neural) instead of the classic block-DCT mark.
- **Buy vs build** → for turnkey crawl+match+takedown at scale evaluate **Vobile**
  and **Pex** (revenue-share, cheaper); cheap pilots via **ACRCloud** (~$26/mo).
  For per-user leak tracing on premium streams use OTT forensic watermarking
  (Irdeto NexGuard / NAGRA / Verimatrix / Friend MTS) via the **DASH-IF A/B**
  model. Get your reference fingerprints into the **free** first-party rights
  tools where piracy actually lands: **YouTube Content ID, Meta Rights Manager,
  TikTok Copyright Match** — they remove at source faster than third-party DMCA.

> Note on the competition: ReelShort, DramaBox, Holywater and Kuku FM publicly
> disclose **no** specific anti-piracy tech and respond reactively. A real
> fingerprint+watermark+takedown program is a genuine differentiator.

## Legal & enforcement (India)

A tiered funnel — most cases never reach court. **Keep a human in the loop;
don't auto-file takedowns from an un-calibrated verdict.**

1. **Detect & document** — build a per-infringement evidence kit: (a) live URL +
   canonical share link, (b) screen recording with a visible clock/date,
   (c) the downloaded file + its **SHA-256 and MD5**, (d) the ContentGuard
   `--evidence` match report (offset + votes + overlap), (e) an independent
   archive snapshot ([web.archive.org](https://web.archive.org/) / perma.cc).
   This maps onto the hash-value-plus-certificate requirement of the **Bharatiya
   Sakshya Adhiniyam 2023** (successor to §65B Evidence Act) so it holds in court.
2. **Tier 1 — platform portals (free, ~24h):** file directly at
   [copyright.sharechat.com](https://copyright.sharechat.com/) and
   [moj-copyright.sharechat.com](https://moj-copyright.sharechat.com/), and to
   the **Rule-3 grievance officer** under the **IT (Intermediary Guidelines)
   Rules, 2021**. Cite the **Copyright Act, 1957** (§51 infringement, §63 criminal).
3. **Tier 1 (parallel) — DMCA:** for any US-hosted layer (CDN, cloud, app-store
   listing, ads/payment partner), a compliant 17 U.S.C. §512(c)(3) notice forces
   removal or the host loses safe harbour.
4. **Tier 2 — legal notice:** lawyer's cease-and-desist citing §51/§63 with a
   15-day deadline (documented pre-suit step).
5. **Tier 3 — court:** for systemic/repeat infringement, a **dynamic "Ashok
   Kumar" (John Doe) injunction** at the Delhi/Bombay High Court (*UTV Software v.
   1337x* lineage) auto-extends to mirror re-uploads. **Direct precedent: the
   Delhi HC (2023) ordered ShareChat & Moj to remove Zee's content** — same
   platforms, same fact pattern. (2026 IT-Rules amendment: court/government-flagged
   content must come down in 3 hours — a court order unlocks the fastest removal.)
6. **Register** key titles' copyright and keep clean masters with the embedded
   ownership watermark — strengthens the §63 criminal route and speeds escalation.

⚠️ **Crawl only PUBLIC surfaces.** Defeating login/anti-bot controls or replaying
a rival's private mobile API can make **you** the defendant under **IT Act §43
(civil, up to ₹5 cr) / §66 (criminal)** and breach-of-contract. Get a one-page
counsel sign-off on exactly what the crawler may touch.

## Files

```
contentguard/
  fingerprint/audio.py   Shazam-style landmark fingerprinting (numpy/scipy)
  fingerprint/video.py   DCT perceptual hashing of frames
  matcher.py             audio offset-histogram + video overlap → verdict
  ingest.py / scan.py    build DB / check suspects (file, folder, URL, watchlist)
  discover.py            search the WHOLE WEB by name for re-uploads (DuckDuckGo keyless + yt-dlp + optional Google CSE); HTML report
  titlematch.py          synonym + fuzzy title matching (catch renamed shows)
  watermark.py           blind block-DCT forensic watermark (embed/detect)
  db.py                  SQLite: reference hashes + persistent detection case log
  report.py              console report + JSON evidence (incl. SHA-256, platform)
  selftest.py            end-to-end proof on synthetic data (no ffmpeg)
  cli.py                 `python -m contentguard ...` (utf-8 / Hindi-safe output)
```

## Before you trust a verdict (calibration)

Thresholds in `config.py` (`MIN_AUDIO_MATCH`, `VIDEO_MAX_HAMMING`,
`VERDICT_*`) were set on **synthetic 30s clips**. Before any verdict drives a
takedown, **re-tune them on your real catalog**: ingest real WOW TV masters,
build a set of real pirate transforms (re-encode, crop, zoom, overlay, flip,
speed, screen-cap), and measure precision/recall **plus a false-positive rate
against a large unrelated corpus**. A `MATCH` that triggers a legal notice needs
a quantified FP rate behind it.

## Out of scope — be honest with stakeholders

Fingerprinting does **not** "solve piracy." It cannot reach, and should not be
sold as covering:

- **Telegram channels, modded/cracked APKs, "free-coin" hacks, offshore
  IPTV/cyberlockers** — no public URL to fingerprint. Needs app-integrity/RASP,
  account-fraud controls, DRM (Widevine L1/FairPlay) and legal escalation.
- **Camera-of-screen re-recording** — defeats both layers and the watermark grid.
- The MVP **watermark** survives JPEG/mild transcode (ownership proof) but **not**
  screen-capture/aspect-crop, and has no error-correction or keyed embedding yet —
  for real **per-user leak tracing**, buy OTT forensic watermarking.
- **Discovery covers the searchable web, not the entire internet.** `discover`
  sweeps the whole web free via DuckDuckGo (keyless) plus YouTube, and the
  Google index too if you add CSE keys — great for the biggest piracy venues and
  any public mirror/blog/free-streaming site. But content behind apps with no
  public search, Telegram channels, or paywalled pages won't surface by name
  search; for those you still feed a URL to `scan`. Note DuckDuckGo rate-limits
  big catalogs — `--throttle` paces the queries; raise it if results thin out.
  There's also **no scheduler** yet (a bot that re-runs `discover` over your
  whole catalog daily) — that's the next build.

This is detection + evidence tooling. The legal takedown is a human process.
