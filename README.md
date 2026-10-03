# 🎓 Convocation Moment Finder: Project Documentation & Learning Guide

## What We Built
We built an end-to-end data pipeline that takes a 6-hour YouTube livestream of a university convocation, transcribes the spoken names, and automatically finds the exact timestamp each student crossed the stage. 

Instead of manually typing out student names, we also built a script to automatically read an official PDF seating chart and extract 2,281 student names. Finally, it cross-references the imperfect AI transcript with the extracted PDF names to output a clean, file (about 45% of students located with ~90% precision; see Round 2) mapping the student to their video timestamp.

---

## 🛑 Problems Faced & ✅ Solutions Chosen

### Problem 1: Getting the Audio from an Ongoing 6-Hour Livestream
*   **Available Solutions:** 
    1. Manually screen-record the stream (takes 6 hours of sitting there).
    2. Wait for the stream to end and download it via standard web tools.
*   **What We Picked:** `yt-dlp` using the `--live-from-start` command.
*   **Why we picked it:** We didn't have 6 hours to wait! This tool allowed us to instantly download the stream's audio from the *very beginning* up to the current point while it was still live.

### Problem 2: Converting 6 Hours of Audio into Text
*   **Available Solutions:**
    1. OpenAI's Cloud API (Very accurate, but costs money and requires you to chop the 6-hour audio into tiny chunks).
    2. Online free websites (Always have size limits, usually max 500MB).
*   **What We Picked:** `faster-whisper` (Python library).
*   **Why we picked it:** It runs 100% locally on your machine for free, has zero size limits, and provides timestamps for every single sentence spoken.

### Problem 3: Getting 2,000+ Names from a PDF Document
*   **The Problem:** The official attendee list was stuck inside a PDF file (`SEATING NUMBERS.pdf`). Copy-pasting 2,281 names from a PDF into Excel manually would take hours and mess up the formatting.
*   **What We Picked:** `pdfplumber` (Python library).
*   **Why we picked it:** PDF text is notoriously hard for computers to read because it's stored as visual coordinates. `pdfplumber` is specifically designed to recognize "tables" inside PDFs and extract them into clean rows and columns in code.

### Problem 4: The AI Misspelling Names (The "Tarish" Problem)
*   **The Problem:** The AI transcribes what it *hears*. If a student is named "Tarush Sardana", the AI might write "Tarish Serdana". A standard exact-match search would fail.
*   **What We Picked:** Fuzzy String Matching using `thefuzz`.
*   **Why we picked it:** Fuzzy matching uses math (Levenshtein distance) to give a "similarity score". It sees "Tarish" and "Tarush" and realizes they are an 85% match, allowing us to map the AI's spelling mistake perfectly back to your official PDF data.

---

## 🛠️ Tools & Libraries Used (The "Why" and "What")

### 1. `yt-dlp` (Command Line Tool)
*   **What it does:** The most powerful open-source YouTube downloader.
*   **Command we used:** `yt-dlp --live-from-start -f bestaudio -o livestream_audio.m4a [YOUTUBE_URL]`
    *   `--live-from-start`: Forces YouTube to give us the video from second 00:00, even if the stream is currently live.
    *   `-f bestaudio`: Ignores the video completely to save space and time.

### 2. `faster-whisper` (Python Library)
*   **What it does:** An optimized, heavily sped-up version of OpenAI's Whisper model.
*   **How we used it:** We used it to transcribe `livestream_audio.m4a` into `transcript.txt`, capturing the timestamp of every spoken word.

### 3. `pdfplumber` (Python Library)
*   **What it does:** A library that visually analyzes PDFs to extract text, tables, and borders perfectly.
*   **How we used it:** We used `page.extract_tables()` to rip the seating chart out of the PDF, loop through the rows, filter out the column headers, and save exactly 2,281 pure names.

### 4. `pandas` (Python Library)
*   **What it does:** The industry standard for handling data and CSVs in Python. 
*   **How we used it:** We used it to easily generate our `attendees.csv` and export our final `matched_timestamps.csv`.

### 5. `thefuzz` (Python Library)
*   **What it does:** Compares two strings of text and tells you how similar they are on a scale of 0 to 100.
*   **How we used it:** We used `process.extractOne()` to find the single most similar spoken sentence in the 6-hour transcript for every official name.

---

### 6. `streamlit` (Python Web Library)
*   **What it does:** Turns Python data scripts into beautiful, interactive web applications in minutes.
*   **How we used it:** We used it to build `app.py`, which reads our final CSV and provides a search box for students. It also automatically embeds the YouTube video jumping to the exact calculated seconds!

---

## 🔧 Round 2: Verification & Fixes (read this first, other AIs!)

An independent check of the first version found the output was NOT reliable. Numbers below are from the real files.

### What was wrong
| # | Problem | Evidence | Fix |
|---|---------|----------|-----|
| 1 | Each student was matched to the *best single line* with `partial_ratio`; a line holds 5-8 names, so many students got the same line, and tiny strings scored 100 | 1,617 of 2,238 rows shared a timestamp; 449 rows matched text under 8 chars ("SO", "ARE") | New matcher scores **word by word** on the 2 best name tokens, per name-chunk, then does a **one-to-one assignment** (a chunk can belong to one student only) |
| 2 | Whisper auto-detected the wrong language in two windows and wrote **Urdu script** | 286 transcript lines, around 2h25-3h05 and 4h00-4h40 | `retranscribe_windows.py` re-runs those windows with `language="en"` -> `transcript_fix.txt`; non-Latin lines are dropped |
| 3 | Speech/lecture lines (before the names start) matched as names | e.g. "a share means being inclusive" -> MANAS SHARMA | Only chunks after minute 145 and with <= 7 words are considered |
| 4 | Timestamps were `MM:SS` with minutes > 60 | `[444:31]` | Output has `Seconds` + `H:MM:SS`; app uses `Seconds` for the YouTube `?t=` link |
| 5 | Threshold 70 and "100% accurate" claim | | Confident = average of the 2 best tokens >= 90 **and** the weaker token >= 80. Everything else goes to `needs_review.csv` |
| 6 | RAM crash on 6-7 h audio, `UnicodeEncodeError` printing to Windows console | | 1-hour chunks (`chunk_transcribe.py`); safe printing |

### Current result (be honest about it)
* Attendees (cleaned, de-duplicated): **2,279**
* Confident matches: **1,019 (~45%)** in `matched_timestamps.csv`
* Needs review / not found: **1,260** in `needs_review.csv` (639 had no usable candidate at all)
* Manual spot check of 30 random confident rows: about **27 correct (~90%)**. Wrong ones were look-alike names, e.g. "Rup Kumar Bansal" for DHRUV KUMAR BANSAL.
* The limit is the speech-to-text quality: the `base` Whisper model on CPU drops/garbles many fast-read names. Next step for more coverage: re-transcribe only the name-calling hours (~2h25 onward) with `small`/`medium` (much faster on a GPU), using the attendee list in `initial_prompt`, then re-run `match_names.py`.

### New / changed files
* `match_names.py`: rewritten (see above). Reads `transcript_original_backup.txt` (copy of the first full transcript) + `transcript_fix.txt`. Writes `transcript_clean.txt`, `matched_timestamps.csv`, `needs_review.csv`.
* `retranscribe_windows.py`: forced-English re-run of the two broken windows (base model, ~13x real time on a Ryzen 7 CPU).
* `app.py`: fuzzy name search (RapidFuzz) with a pick-list, shows the embedded video at the right second; if the name is only in `needs_review.csv` it says "not located yet" instead of showing a wrong video.
* `requirements.txt`: `streamlit`, `pandas`, `rapidfuzz`.
* Old output `matched_timestamps_NEW.csv` is the unreliable first version; do not deploy it.

### Tools added in Round 2
* `rapidfuzz`: fast fuzzy string matching (edit-ratio and Jaro-Winkler). Jaro-Winkler is forgiving about spelling errors at the end of a word, which suits Indian names transcribed phonetically.
* `numpy` `cdist` / `reduceat`: scores thousands of (student word x transcript word) pairs in one matrix operation, then takes the best word per chunk.

---

## 🚀 How to Run & Deploy This Project

### Part 1: Generating the Data (Backend)
1. **Step 1: Download & Transcribe (`chunk_transcribe.py`)**
   Downloads the YouTube audio, splits it into 1-hour chunks (to save RAM), and creates `transcript.txt`.
   ```bash
   python chunk_transcribe.py
   ```

2. **Step 2: Extract Data from PDF (`extract_pdf.py`)**
   Reads `SEATING NUMBERS.pdf` and automatically extracts 2,281 names into `attendees.csv`.
   ```bash
   python extract_pdf.py
   ```

3. **Step 3: Match Names & Timestamps (`match_names.py`)**
   Run `python retranscribe_windows.py` first (fixes the Urdu-script windows), then this script cross-references `attendees.csv` with the transcript (see Round 2).
   ```bash
   python match_names.py
   ```
   *Result:* Outputs `matched_timestamps.csv` (confident) and `needs_review.csv`.

### Part 2: The Web App (Frontend)
4. **Step 4: Run the Web App Locally**
   To test the web app on your own computer:
   ```bash
   pip install streamlit pandas rapidfuzz
   streamlit run app.py
   ```

5. **Step 5: Deploying for Free to the Internet**
   * Upload `app.py`, `matched_timestamps.csv`, `needs_review.csv`, and `requirements.txt` to a new GitHub repository.
   * Go to [Streamlit Community Cloud](https://share.streamlit.io/).
   * Connect your GitHub repo and click **Deploy**. You will get a free public URL to share with students!
