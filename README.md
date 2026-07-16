# WOW TV - Piracy Finder

A tool to find where WOW TV micro-drama shows have been re-uploaded on other
platforms. You give it a show title, and it searches the web and YouTube for that
title (including renames, spelling tricks, and regional translations), keeps only
real video links from known platforms, and gives you a clean table plus a
downloadable CSV sheet of the flagged links.

It works at the **title level only** - it does not analyse the audio or video
inside a clip. A title match is a strong lead, not proof: anyone can name a video
the same thing. Always open each link to confirm before acting on it.

**Made by Kratin Sharma.**
For any issues or questions, reach out to me (Kratin Sharma) on **Slack**.

---

## Important: you must have the show list (sheet) yourself

This tool does NOT come with WOW TV's show list. That sheet is our internal data,
so it is intentionally kept OUT of this repository - it cannot be made public on
GitHub. Everyone who uses the tool has to keep the sheet with them and add the
show names themselves. There are two ways:

1. **Just paste the show names** into the website (one per line). Simplest, no
   file needed.
2. **Use a `shows.csv` file** if you want to scan many shows at once from a file.
   It must be named exactly `shows.csv`, have a column header `title`, and sit
   inside the project folder. You can create it from the WOW TV Live Tracker
   sheet (see "Generating shows.csv" below).

Keep `shows.csv` and the Excel sheet on your own computer. Do not upload them to a
public place.

---

## One-time setup

1. Install **Python 3** (during install, tick "Add Python to PATH").
2. Download this repo: green **Code** button -> **Download ZIP** (or `git clone`),
   then unzip.
3. Open a terminal in the project folder and install requirements:
   ```
   pip install -r requirements.txt
   ```

---

## On Mac or Linux

Exactly the same tool, just use `python3` / `pip3` and a few different commands:

- Install:  `pip3 install -r requirements.txt`
- Run:      `python3 app.py`  (browser opens at http://127.0.0.1:8000)
- Open a saved report:  `open leads.html`  (on Linux: `xdg-open leads.html`)
- Change the port:  `PORT=8001 python3 app.py`
- Copy a file into the folder:  use `cp` instead of `copy`

The `yt-dlp.exe` in the repo is Windows-only. On Mac/Linux you do NOT need it -
`pip3 install -r requirements.txt` installs yt-dlp automatically. Just ignore the
.exe file. Everything else (the website, the settings, the CSV) is identical.

---

## How to operate it - the website (easiest)

1. Open a terminal in the project folder:
   ```
   cd "C:\Users\admin\Desktop\wowTV_title_privacy"
   ```
2. Start it:
   ```
   python app.py
   ```
   The browser opens automatically at `http://127.0.0.1:8000`.
3. On the page:
   - **Shows box:** type or paste the show names, one per line.
   - **Threshold:** how strict the matching is. Start at 60.
   - **Limit:** how many results to fetch per search. Start at 15-20.
   - **Hide your own channels:** keep `wowtv,kuku` so WOW TV's own uploads are hidden.
   - **Regional translation:** leave OFF for speed; tick it only to also catch
     Tamil/Telugu/etc. dub re-uploads (slower).
   - **Video links only:** keep it ON.
4. Click **Scan**. Each show takes about 10-20 seconds.
5. Read the table (grouped by show). **EXACT** matches are at the top and are the
   strongest leads. Each row has the platform, the found title, and a clickable link.
6. Click **Download CSV** to save the sheet (opens in Excel / Google Sheets).
7. To stop the website: go back to the terminal and press `Ctrl + C`.

---

## How to operate it - command line (for many shows / a file)

One show:
```
python -m contentguard discover "Gymwala Billionaire" --limit 20 --threshold 60 --exclude "wowtv,kuku" --report leads.html
```
Many shows from a file (`shows.csv`, or a plain `.txt` with one title per line):
```
python -m contentguard discover shows.csv --limit 20 --threshold 60 --exclude "wowtv,kuku" --report leads.html --json leads.json
```
- `--report leads.html` makes a clickable HTML report (open it, or run `start leads.html`).
- `--json leads.json` saves the results as structured data.

---

## Identifying links you already have (e.g. Facebook share links)

Search engines cannot FIND Facebook `/share/` links - the URL is an opaque id and
that format is not indexed, so search will never surface them. But if you already
HAVE such links (found manually, or forwarded on WhatsApp), the tool can open each
one, read its caption, confirm it is still live, and match it to a show.

- **Website:** paste the links into the "Or paste suspect links to identify" box
  and click Scan.
- **Command line:**
  ```
  python -m contentguard check links.txt --csv found.csv
  ```
  (or pass the links directly instead of a file).

Important: many pirate reels use generic clickbait captions ("Pati ne choda",
"Kya hua", "Paise") that do NOT contain the show title, so they show as "not
identified". That is honest - such a caption cannot be mapped to a specific show
from text alone. What still helps: the tool shows the caption and the uploader,
and if one account is posting many of your shows, report that whole account. For
a definitive show ID you would need content fingerprinting (matching the actual
audio/video), which is out of scope for this title-based tool.

## Sharing the sheet with other people

The sheet is not on GitHub, so you share it separately (Slack / Drive / email).
For it to work on someone else's machine:

- **If you send a CSV:** tell them to rename it to exactly `shows.csv`, make sure
  the first row has a column header `title`, and drop it inside the project folder.
  Then the command-line mode reads it directly.
- **If you send the Excel tracker (`.xlsx`):** the file name does not matter. They
  run the extractor and point it at the file (see below), which creates `shows.csv`.
- **If they only use the website:** no file needed - they just paste the titles.

### Generating shows.csv from the Excel tracker
```
python extract_catalog.py "C:\path\to\WowTV Show Live Tracker.xlsx"
```
This writes `shows.csv`. To also build the "currently-live shows only" list:
```
python make_priority.py
```
(creates `priority_shows.csv`).

---

## Swapping in a NEW sheet later

When the tracker is updated and you want the tool to use the new shows:

1. Download the new tracker (`.xlsx`).
2. Run the extractor on the new file - it overwrites `shows.csv` with the new shows:
   ```
   python extract_catalog.py "C:\path\to\NEW sheet.xlsx"
   ```
3. (Optional) refresh the live-shows list:
   ```
   python make_priority.py
   ```
That is it - the tool now uses the new catalog. (If you maintain `shows.csv` by
hand instead, just replace that file with the new one, keeping the `title` column.)

---

## Settings explained

- **threshold** (0-100): minimum match score for a link to show.
  - Higher = stricter (less noise). Lower = more results (more noise).
  - Distinctive titles (e.g. "Banarasiya Mafia"): 55-60 is clean.
  - Generic titles (e.g. "Doctor Princess", "Fake Wife"): use 70 or more.
- **limit:** results fetched per search query. Higher = more thorough but slower.
  15-25 is a good range. (This is the tool's own setting, unrelated to any account
  usage limit.)
- **exclude:** comma list of words to hide (your own channels), e.g. `wowtv,kuku`.
  Matching ignores spaces and case, so `wowtv` also hides "WoW TV - Hindi" and
  "Wowtv_Shows".
- **Regional translation:** off by default (slower). Turn on to also search
  Tamil/Telugu/Kannada/Malayalam/Hindi titles for dub re-uploads.

---

## How the matching is kept relevant

- Distinctive words (bhikhari, gymwala, banarasiya) carry the match; common trope
  words (boss, billionaire, love) barely count - so "Bigg Boss" is not confused
  with "Bhikhari Boss".
- Handles spelling and spacing tricks ("Gym Wala" = "Gymwala", "Doctr Princess" =
  "Doctor Princess").
- Only single videos from known platforms (YouTube, Dailymotion, ok.ru, Facebook,
  Instagram, ShareChat/Moj, Rumble, MicroTV, etc.). Channels, profiles, tag pages,
  and random non-video sites are filtered out.

---

## Troubleshooting (common issues)

**"python is not recognized" / "pip is not recognized"**
Python is not installed or not on PATH. Reinstall Python 3 and tick "Add Python to
PATH", then reopen the terminal.

**"ModuleNotFoundError: No module named 'ddgs' / 'rapidfuzz' / 'openpyxl' / 'deep_translator'"**
You skipped the install step. Run:
```
pip install -r requirements.txt
```

**Website does not open in the browser**
Open it manually: go to `http://127.0.0.1:8000` in any browser.

**"Address already in use" / port 8000 busy**
An old copy is still running. Close that terminal (or press `Ctrl + C` in it), then
start again. Or change the port:
```
set PORT=8001
python app.py
```
and open `http://127.0.0.1:8001`.

**0 results, or far fewer than expected**
- You may have run many shows quickly and DuckDuckGo rate-limited you. Wait a few
  minutes, scan fewer shows at a time, or add `--throttle 2` on the command line.
- The threshold may be too high for that title. Lower it (e.g. 55).
- Generic titles genuinely return less when strict - that is expected.
- DuckDuckGo gives slightly different results each run; running again or raising
  `--limit` to 25-30 can surface more.

**Too many irrelevant links**
Raise the threshold (try 70+), especially for generic titles.

**YouTube results missing**
yt-dlp must be available. Keep `yt-dlp.exe` in the folder, or install it:
```
pip install yt-dlp
```

**Regional (Tamil/Telugu/...) titles look like boxes in the terminal**
That is just the terminal font - the data is fine. Use the website, or open the
CSV in Excel/Google Sheets where it displays correctly.

**"shows.csv" not found, or it reads nothing**
The file must be named exactly `shows.csv`, sit in the project folder, and have a
column header `title` in the first row.

**extract_catalog.py cannot find the sheet**
Pass the full path in quotes, e.g.
`python extract_catalog.py "C:\Users\you\Downloads\WowTV Show Live Tracker.xlsx"`.

**Antivirus flags yt-dlp.exe**
yt-dlp is a well-known open-source downloader; this is a false positive. You can
also remove the exe and use `pip install yt-dlp` instead.

**The tool shows WOW TV's own uploads**
Keep `wowtv,kuku` in the exclude box / `--exclude "wowtv,kuku"`.

**Hosting it online (Vercel/Render) returns nothing**
Search engines block automated requests from cloud server IPs, and the scans are
too long for serverless. Run it on a normal computer instead.

---

## Pushing updates to GitHub (for whoever maintains it)

After changing any file:
```
git add -A
git commit -m "describe what changed"
git push
```
If `git push` says "Repository not found": the repo name/owner is wrong, or you are
signed in to GitHub as the wrong account. If a remote is already set wrong, fix it
with `git remote set-url origin https://github.com/USER/REPO.git`.

---

## Limitations

- Web search only finds content on the public web. Content inside an app (e.g. a
  rival app's in-app catalog) is not on the public web and cannot be found by any
  web search. For those, use the platform's copyright portal.
- DuckDuckGo and YouTube can rate-limit or block automated requests from cloud
  server IPs, so this runs best on a normal computer.
- A title match is a lead, not proof. Confirm each link before any takedown.

---

Made by **Kratin Sharma**. Issues or questions: reach out to me on **Slack**.
