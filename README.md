# WOW TV - Piracy Finder

A simple tool to find where WOW TV micro-drama shows have been re-uploaded on
other platforms. You give it a show title; it searches the web and YouTube for
that title (including renames, spelling tricks, and regional translations),
keeps only real video links from known platforms, and gives you a clean table
and CSV of the flagged links.

It works at the title level only - it does not analyse the audio or video inside
a clip. A title match is a strong lead, not court proof: anyone can name a video
the same thing. Open each link to confirm, and for legal action confirm the clip
by content/fingerprint.

by Kratin Sharma

## What it does

- Searches the whole web (DuckDuckGo, keyless) plus YouTube for the title and
  its likely renames.
- Catches spelling and spacing tricks pirates use ("Gym Wala" = "Gymwala",
  "Doctr Princess" = "Doctor Princess").
- Weights distinctive words over common trope words, so "Bigg Boss" does not get
  confused with "Bhikhari Boss".
- Optionally translates the title into Hindi/Tamil/Telugu/Kannada/Malayalam to
  catch dubbed re-uploads.
- Returns only real single-video links from known platforms (YouTube,
  Dailymotion, ok.ru, Facebook, Instagram, ShareChat/Moj, Rumble, MicroTV, etc.).
  Channels, profiles, tag pages, and random non-video sites are filtered out.

## Setup (one time)

```bash
pip install -r requirements.txt
```

## Run the website (easiest)

```bash
python app.py
```
The browser opens automatically. Paste show names (one per line), click Scan,
and you get a table of links plus a Download CSV button.

## Run from the command line

```bash
python -m contentguard discover "Gymwala Billionaire" --limit 25 --threshold 60 --exclude "wowtv,kuku" --report leads.html
```

You can also pass a text/CSV file of many show names instead of one name.

## Settings explained

- **threshold** (0-100): the minimum match score for a link to be shown. Higher
  = stricter (only very close matches). Lower = more results, more noise.
  - Distinctive titles ("Banarasiya Mafia"): 55-60 is clean.
  - Generic titles ("Doctor Princess", "Fake Wife"): use 70+.
- **limit**: how many search results to fetch per query. Higher = more thorough
  but slower. 15-25 is a good range.
- **exclude**: comma list of words to hide (your own channels), e.g.
  `wowtv,kuku`. Matching ignores spaces and case, so `wowtv` also hides
  "WoW TV - Hindi" and "Wowtv_Shows".
- **Regional translation**: off by default (it is slower). Turn it on to also
  search Tamil/Telugu/etc. titles for dub re-uploads.

## Note on data

Your internal show catalog (the exported sheet) is intentionally NOT included in
this repository - it is listed in `.gitignore`. Generate it locally from your
own sheet:

```bash
python extract_catalog.py "path/to/your sheet.xlsx"
```

## Limitations

- Web search can only find content on the public web. Content inside an app
  (for example a rival app's in-app catalog) is not on the public web and cannot
  be found by any web search. For those, use the platform's copyright portal.
- DuckDuckGo and YouTube can rate-limit or block automated requests from cloud
  server IPs, so this runs best on a normal computer.
