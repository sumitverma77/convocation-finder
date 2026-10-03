# Convocation Moment Finder

Type your name, get the YouTube link to the exact moment you were called on stage at the
VIT Bhopal 7th convocation (6+ hour livestream).

## What kind of project is this?
A **Python data / AI pipeline plus a small web app**. It is applied AI, not model training:

| Part | Kind | Tools |
|---|---|---|
| Speech to text | Pre-trained AI model (inference only) | `faster-whisper` (Whisper), YouTube auto-captions |
| Name matching | Classic NLP / fuzzy string matching (not ML) | `rapidfuzz`, `numpy` |
| Data handling | Data engineering (ETL) | `pandas`, `pdfplumber`, `ffmpeg`, `yt-dlp` |
| Web app | Frontend | `streamlit` |

Pipeline: **audio -> transcripts (2 sources) -> match against the attendee list -> CSV -> search app.**

## Privacy
The attendee list was shared internally. The published files (`data/processed/`) contain only name, status, timestamps and confidence: no branch, registration number or seat. Inputs (`data/raw`, `data/interim`) are git-ignored.

## Layout
```
app.py                    Streamlit app (deployed). Reads data/processed/*.csv
pipeline/                 Offline steps, run in order (python -m pipeline.<name>)
  config.py               every file path in one place
  extract_attendees.py    1. seating PDF -> attendee names
  transcribe_audio.py     2. audio -> Whisper transcript (1-hour chunks)
  retranscribe_windows.py 3. re-run stretches where Whisper detected the wrong language / dropped names (config.FIX_WINDOWS)
  build_yt_transcript.py  4. YouTube captions (VTT) -> same transcript format
  match_names.py          matcher (fuzzy, per-word, one-to-one)
  combine_results.py      5. run matcher on both transcripts, add the expected-time prior, write results
  export_review.py        6. (optional) sheet of doubtful students to fill in by hand; answers feed back into step 5
data/raw/                 audio, VTT, PDF            (git-ignored)
data/interim/             transcripts, attendee list (git-ignored)
data/manual/              review_sheet.xlsx you fill in (git-ignored)
data/processed/           results.csv (one row per student), candidates.csv (top 3 moments each)  (committed, used by the app)
tests/                    pytest unit tests for the matcher
docs/LEARNING_GUIDE.md    what we built, problems faced, solutions, tools explained
requirements.txt          app dependencies (Streamlit Cloud)
requirements-pipeline.txt pipeline dependencies (your machine)
```

## Run the app
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Re-run the pipeline
Needs `ffmpeg` and `yt-dlp` installed, and the audio / PDF placed in `data/raw/`.
```bash
pip install -r requirements-pipeline.txt
yt-dlp -f bestaudio -o data/raw/livestream_audio.m4a "https://www.youtube.com/watch?v=iZuGjFTKXL8"
yt-dlp --skip-download --write-auto-subs --sub-langs en-orig --sub-format vtt -o data/raw/yt_captions "https://www.youtube.com/watch?v=iZuGjFTKXL8"
python -m pipeline.extract_attendees
python -m pipeline.transcribe_audio
python -m pipeline.retranscribe_windows
python -m pipeline.build_yt_transcript
python -m pipeline.combine_results
python -m pytest
```

## How a result is decided
Each student gets a **status** and up to 3 **candidate moments**, each with a confidence score (shown in the app):

* **confident**: both transcripts (Whisper + YouTube captions) found the name at the same time, or one found it very clearly, and the time fits where the student was expected.
* **possible**: we have candidates but are not sure; the app shows up to 3 videos side by side with scores.
* **none**: nothing usable; the app shows the time window in which students seated near them were called.

**Expected-time prior.** Students from the same programme and seat row are called in the same part of the ceremony. From confident matches we learn an expected time per group (computed only in memory); cross-validated this predicts a student's time to within about 11 minutes (median) versus 87 minutes with no prior. Candidates inside the window get a bonus, far outside get a penalty, and weaker names are searched only inside the window.
Two safeguards: the two best name tokens must match *different* spoken words, and very common tokens (KUMAR, SINGH, SHARMA...) cannot identify a student alone.

## Manual review (you tell us the doubtful ones)
```bash
python -m pipeline.export_review      # writes data/manual/review_sheet.xlsx
```
Open the sheet: each row is a doubtful student with up to 3 clickable options (jump straight to the second). In the yellow `your_answer` column type `1`/`2`/`3` (that option is right), a time like `4:35:57` (none of them is), or `x` (not in the recording). Save, then re-run `python -m pipeline.combine_results`; those students become **confirmed** (100%, "verified by hand"). Re-exporting keeps your earlier answers.

## What improved accuracy (and why)
* **Whisper repair windows**: in some stretches (e.g. 4:22-4:40) Whisper wrote Urdu script or dropped names, leaving YouTube alone. Those stretches (found by comparing line counts per 10 minutes) are re-transcribed in forced English without the voice-activity filter. Whisper is not deterministic, so an earlier second sample (`transcript_fix_b.txt`) is kept as extra evidence.
* **Per-name time from YouTube captions** (about one name per line) when both sources agree, so the link lands on the name.
* **Matching rules**: two name tokens must match different spoken words; common surnames cannot identify a student alone; very short spoken words ("my") are discounted; a long uncommon first name alone gives only a capped "possible" candidate (e.g. "Shambhabi teach her" for SHAMBHAVI JHA).
* **One spoken name = one student**: if several students would be "confident" for the same moment, only a clear winner keeps it.
* **Known answers**: `data/manual/known_answers.csv` (`name,time`) lets you type in moments you read from the subtitles; they become "confirmed".

## Current results
Of 2,389 attendees: about 1,340 confident or confirmed (56%), about 1,020 possible (candidates shown), about 30 none. Manual spot checks of the confident group: 30 of 30 plausible in the latest sample, about 90-95% over several samples. See `docs/LEARNING_GUIDE.md` for history and the next ideas (bigger Whisper model on the name-calling hours, a stage-order model).

## Deploy
Streamlit Community Cloud: repo `sumitverma77/convocation-finder`, branch `main`, main file `app.py`.
