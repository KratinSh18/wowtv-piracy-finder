# WOW TV - Piracy Finder

A tool to find where WOW TV micro-drama shows have been re-uploaded on other
platforms. You give it a show title, and it searches the web and YouTube for
that title (including renames, spelling tricks, and regional translations),
keeps only real video links from known platforms, and gives you a clean table
and a downloadable CSV sheet of the flagged links.

It works at the **title level only** - it does not analyse the audio or video
inside a clip. A title match is a strong lead, not proof: anyone can name a
video the same thing. Always open each link to confirm before acting on it.

**Made by Kratin Sharma.**
For any issues or questions, reach out to me (Kratin Sharma) on **Slack**.

---

## Important: you need your show list (catalog)

This tool does not come with WOW TV's show list - that data is kept private and
is intentionally NOT in this repository. You must have the show titles with you
to search them. There are two ways:

1. **Just type/paste the show names** into the website (one per line). This is
   the simplest way and needs no file.
2. **Use a `shows.csv` catalog file.** If you want to scan many shows at once
   from a file, you need a `shows.csv` (a spreadsheet with a `title` column).
   Generate it from the WOW TV Live Tracker sheet:
   ```
   python extract_catalog.py "C:\path\to\WowTV Show Live Tracker.xlsx"
   ```
   This reads the sheet and writes `shows.csv` (and you can also run
   `python make_priority.py` to make `priority_shows.csv` with only the
   currently-live shows). Keep these CSV files on your own computer - do not
   upload them publicly.

---

## One-time setup

1. Install Python 3 (if not already installed).
2. Open a terminal in this folder and install the requirements:
   ```
   pip install -r requirements.txt
   ```

---

## How to operate it (the website - easiest)

1. Open a terminal in this folder:
   ```
   cd "C:\Users\admin\Desktop\wowTV_title_privacy"
   ```
2. Start the website:
   ```
   python app.py
   ```
   Your browser opens automatically at `http://127.0.0.1:8000`.
3. In the page:
   - **Shows box:** type or paste the show names, one per line.
   - **Threshold:** how strict the matching is (see "Settings" below). Start at 60.
   - **Limit:** how many results to fetch per search. Start at 15-20.
   - **Hide your own channels:** keep `wowtv,kuku` so WOW TV's own uploads are hidden.
   - **Regional translation:** leave OFF for speed; tick it only if you want to
     also catch Tamil/Telugu/etc. dub re-uploads (it is slower).
   - **Video links only:** keep it ON.
4. Click **Scan**. Each show takes about 10-20 seconds.
5. You get a table grouped by show:
   - **Score** = how close the match is (higher = closer). Items marked **EXACT**
     are at the top - these are the strongest leads.
   - **Platform**, **Found title**, and a clickable **Link**.
6. Click **Download CSV** to save the whole sheet (opens in Excel / Google Sheets).
7. To stop the website, go back to the terminal and press `Ctrl + C`.

---

## How to operate it (command line - for many shows / automation)

Scan one show:
```
python -m contentguard discover "Gymwala Billionaire" --limit 20 --threshold 60 --exclude "wowtv,kuku" --report leads.html
```
Scan many shows from a file (`shows.csv` or a plain text file, one title per line):
```
python -m contentguard discover shows.csv --limit 20 --threshold 60 --exclude "wowtv,kuku" --report leads.html --json leads.json
```
- `--report leads.html` writes a clickable HTML report.
- `--json leads.json` writes the results as structured data.
- Open the HTML report by double-clicking it, or run `start leads.html`.

---

## Settings explained

- **threshold** (0-100): minimum match score for a link to be shown.
  - Higher = stricter (only very close matches, less noise).
  - Lower = more results, but more noise.
  - Distinctive titles (e.g. "Banarasiya Mafia"): 55-60 is clean.
  - Generic titles (e.g. "Doctor Princess", "Fake Wife"): use 70 or more.
- **limit:** how many search results to fetch per query. Higher = more thorough
  but slower. 15-25 is a good range. (This is the tool's setting - it has nothing
  to do with any account usage limit.)
- **exclude:** comma list of words to hide (your own channels), e.g.
  `wowtv,kuku`. Matching ignores spaces and case, so `wowtv` also hides
  "WoW TV - Hindi" and "Wowtv_Shows".
- **Regional translation:** off by default (slower). Turn it on to also search
  Tamil/Telugu/Kannada/Malayalam/Hindi titles for dub re-uploads.

---

## How the matching is kept relevant

- Distinctive words (bhikhari, gymwala, banarasiya) carry the match; common trope
  words (boss, billionaire, love) barely count - so "Bigg Boss" is not confused
  with "Bhikhari Boss".
- It handles spelling and spacing tricks pirates use ("Gym Wala" = "Gymwala",
  "Doctr Princess" = "Doctor Princess").
- Only single videos from known platforms (YouTube, Dailymotion, ok.ru, Facebook,
  Instagram, ShareChat/Moj, Rumble, MicroTV, etc.) are shown. Channels, profiles,
  tag pages, and random non-video websites are filtered out.

---

## Limitations

- Web search only finds content on the public web. Content inside an app (for
  example a rival app's in-app catalog) is not on the public web and cannot be
  found by any web search. For those, use the platform's copyright portal.
- DuckDuckGo and YouTube can rate-limit or block automated requests from cloud
  server IPs, so this runs best on a normal computer (not a cloud host).
- A title match is a lead, not proof. Confirm each link before any takedown.

---

Made by **Kratin Sharma**. Issues or questions: reach out to me on **Slack**.
