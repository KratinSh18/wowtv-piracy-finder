# WOW TV — Title Privacy / Anti-Piracy Tool 🛡️

Bhai, ye tool tera WOW TV ka **"Content ID by title"** hai. Tu show ka naam daalta hai,
ye **pura internet** scan karta hai aur batata hai ki wahi show (ya AI se **renamed**
version — jaise *Billionaire Boyfriend → Rich Boyfriend*) kisi aur platform pe
upload to nahi ho gaya. **Sirf title pe kaam karta hai** — audio/video ke andar
nahi jaata (tune wahi bola tha).

> ⚠️ Ek baat hamesha yaad rakh: **title match = LEAD hai, court-proof nahi.** Koi bhi
> apne show ka naam "Rich Boyfriend" rakh sakta hai. Isse shortlist banta hai —
> phir us clip ko download karke fingerprint se confirm karte hai (neeche "Pakka
> proof" dekh).

---

## 0) Ek baar ka setup

```powershell
cd "C:\Users\admin\Desktop\wowTV_title_privacy"
pip install -r requirements.txt
```
(`ddgs` = keyless web search, `openpyxl` = sheet padhne ke liye. yt-dlp optional.)

---

## Files ka matlab

| File | Kya hai |
|---|---|
| `shows.csv` | Teri sheet ke **saare 876 titles** (Show Name + original IP title, dedup) |
| `priority_shows.csv` | Sirf **157 live-tracker shows** (abhi air ho rahe — sabse zyada risk) |
| `piracy_report.html` | **Deep AI scan ka result** — STRONG/POSSIBLE leads, clickable (main cheez) |
| `piracy_report.csv` | Wahi result, Excel mein khulne wala (records/takedown tracking) |
| `extract_catalog.py` | Sheet update ho to dobara `shows.csv` banata hai |
| `contentguard/` | Engine (title match + keyless web search + fingerprint) |
| `ENGINE_README.md` | Poori technical detail |

---

## 1) Sabse aasaan — ek show check kar (keyless, abhi chalega)

```powershell
python -m contentguard discover "Billionaire Boyfriend" --exclude "wow tv,wowtv,kuku" --report leads.html
```
- `--exclude` = tere apne channels chhupa deta hai (taaki sirf dusron ke uploads dikhe).
- `--report leads.html` = browser mein khulne wali clickable report.
- AI khud synonym variants search karta hai: *rich boyfriend, wealthy boyfriend, billionaire lover*...

## 2) Puri catalog ek saath (file se)

```powershell
# 157 high-risk live shows (recommended pehle ye chala):
python -m contentguard discover priority_shows.csv --exclude "wow tv,wowtv,kuku" --threshold 60 --report leads.html

# ya pura 876:
python -m contentguard discover shows.csv --exclude "wow tv,wowtv,kuku" --threshold 65 --report leads_all.html
```
- **Default `--threshold 60` rakh** — ab matching smart hai (neeche dekh), to 60 pe
  kachra apne aap nikal jaata hai. Sirf bohot pakke chahiye → 75. Zyada recall → 50.
- **`--limit` = har search query pe kitne results laaye** (default 20). Zyada =
  zyada uploads milenge par thoda slow. Recall ke liye `--limit 25` ya `30`.
- DuckDuckGo bohot tezi se chalane pe rate-limit karta hai — bada catalog ho to
  `--throttle 2` laga de. DDG har baar thode alag results deta hai, to ek hi show
  do baar chalane pe naye links bhi mil sakte hai.
- 🌐 Title ko **Hindi/Tamil/Telugu/Kannada/Malayalam** mein translate karke native
  script mein bhi search karta hai (dub re-uploads ke liye).

**Smart matching (kyun ab kachra nahi aata):**
- ⚖️ **Common trope words ka weight kam** — "boss / billionaire / wife / love" har
  doosre title mein hote hai, to akele inse match = ignore. **Distinctive word**
  ("bhikhari, gymwala, banarasiya") match hona zaroori hai. Isliye *Bigg Boss* /
  *Baby Boss* ab *Bhikhari Boss* se match **nahi** hote (pehle 63 score aata tha → ab ~4).
- 🔡 **Typo/spacing** ("Doctr Princess", "Gymwal Billionare", "Gym Wala") → EXACT.
- 🎬 **Sirf single-video links** — channel/profile/tag/playlist (jaise `@channel`,
  `/tag/`) drop ho jaate, bas asli video URLs.

**Naye defaults (apne aap ON):**
- 🎬 **Sirf video links** dikhte hai (YouTube, Dailymotion, ok.ru, Moj/ShareChat,
  microtv jaisi sites). Script/text pages (Wattpad, Wikipedia, IMDb, books) filter
  ho jaate. Agar sab links chahiye to `--all-links` laga.
- 🌐 **Regional translation**: title ko Hindi/Tamil/Telugu/Kannada/Malayalam mein
  translate karke bhi dhundhta hai (dubbed re-uploads ke liye). Badalna ho to
  `--langs "hi,ta,te,kn,ml,bn,mr"`. Band karna ho to `--no-translate`.
- 🎯 **EXACT match sabse upar**, phir broad. Title pe match karta hai — YT channel
  ka naam same ho to usse flag nahi karta.
- 🔤 **Typo/spelling tricks bhi pakadta hai**: "Doctr Princess", "Gymwal Billionare",
  "Bilionaire Boyfreind", ya spacing "Gym Wala" — sab EXACT jaise top pe aate hai
  (pirates jaan-bujhke 1-2 letter udate hai bachne ke liye, ab woh nahi bachega).
- 📺 **Moj/ShareChat/Dailymotion** ko seedha probe karta hai (recall ke liye).

## 3) Deep AI scan (jo maine abhi chalaya)

`piracy_report.html` isi ka output hai — 157 live shows pe AI ne rename variants
bana ke web hunt kiya, phir ek skeptic AI ne har lead ko **STRONG / POSSIBLE /
NOISE** mein chhaant diya (Wikipedia/IMDb/books jaisa noise hata diya). Bas double-click.

---

## Result kaise padhe

- 🔴 **STRONG** = title bilkul match ya clear translation/rename, aur kisi
  third-party **video platform** pe (YouTube re-upload channel, Dailymotion, ok.ru,
  ShareChat/Moj, free-drama sites). Ye pehle dekh.
- 🟠 **POSSIBLE** = ho sakta hai, par pakka nahi (generic naam / platform clear nahi).
- ⚪ **NOISE** = ignore (alag show, news, book, dating page, ya tera apna listing).

---

## ⚠️ Apps ke andar ka content (Moj app waala sawaal)

Tune Moj **app** mein "Doctor Princess" dekha par tool mein nahi aaya — iski wajah
samajh le, ye tool ki kami nahi, **internet ki limit** hai:

- Web search (Google/DuckDuckGo) sirf woh cheez dhundh sakta hai jo **public
  internet pe indexed** ho — YouTube, Dailymotion, ok.ru, free-streaming sites,
  blogs. Ye sab ye tool pakad leta hai.
- **App ke andar ka catalog (Moj app, koi bhi app) public web pe nahi hota** —
  isliye koi bhi web search (ye tool, ya khud Google) uske andar nahi dekh sakta.
  App ke andar dekhne ke liye **us app mein hi search karna padta hai**.

Toh Moj-jaise app content ke liye 2 raaste:
1. **Share link nikaal:** Moj app mein show pe **Share** dabaa → `moj.sharechat.com/...`
   link milega → us link ko `scan` kar ke evidence bana (neeche). App ke andar
   manually dhundhna padega, par evidence pakka ban jaayega.
2. **Moj/ShareChat copyright portal:** `copyright.sharechat.com` /
   `moj-copyright.sharechat.com` pe apna title daal — wo apne **poore catalog**
   (app + web) mein match karke takedown karte hai. App ke andar tak yahi pahunchta hai.

> Matlab: **web pe jo khula pada hai wo ye tool dega; app ke andar ke liye share-link
> + copyright portal.** Jaisa tune kaha — Moj pe hai to YouTube/Dailymotion pe bhi
> hoga, aur wo ye tool pakad lega.

## Pakka proof (takedown ke liye) — content fingerprint

Title se shortlist bani. Ab us **ek clip** ko pakka karne ke liye:
```powershell
python -m contentguard scan "<us-video-ka-url>" --evidence case.json
```
Ye audio/video fingerprint se confirm karta hai ki wahi WOW TV ka content hai —
even agar crop/logo/mirror/re-encode kiya ho. `case.json` mein SHA-256 + match
evidence aata hai jo takedown/legal ke kaam aata hai. (Real catalog aane ke baad
apne masters `ingest` kar dena — phir ye sabse strong route hai.)

---

## Sheet update ho to (naye shows aaye)

```powershell
python extract_catalog.py "C:\path\to\naya WowTV Show Live Tracker.xlsx"
python make_priority.py        # priority_shows.csv refresh
```

---

## Takedown — short version (India)

1. Evidence rakh: live URL + screen recording (date dikhe) + downloaded file ka
   SHA-256 + `case.json`.
2. ShareChat/Moj copyright portal (copyright.sharechat.com / moj-copyright.sharechat.com)
   aur platform ka grievance officer — Copyright Act 1957 cite kar.
3. US-hosted ho to DMCA notice.
4. Repeat offender → lawyer notice → Delhi/Bombay HC dynamic injunction (Moj/ShareChat
   pe pehle se precedent hai). Detail `ENGINE_README.md` mein.

⚠️ Sirf **public** pages crawl kar — login/app ke andar ghusna legal panga hai.
