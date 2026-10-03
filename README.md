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

## Layout
```
app.py                    Streamlit app (deployed). Reads data/processed/*.csv
pipeline/                 Offline steps, run in order (python -m pipeline.<name>)
  config.py               every file path in one place
  extract_attendees.py    1. seating PDF -> attendee names
  transcribe_audio.py     2. audio -> Whisper transcript (1-hour chunks)
  retranscribe_windows.py 3. re-run stretches where Whisper detected the wrong language
  build_yt_transcript.py  4. YouTube captions (VTT) -> same transcript format
  match_names.py          matcher (fuzzy, per-word, one-to-one)
  combine_results.py      5. run matcher on both transcripts, merge, write results
data/raw/                 audio, VTT, PDF            (git-ignored)
data/interim/             transcripts, attendee list (git-ignored)
data/processed/           matched_timestamps.csv, needs_review.csv  (committed, used by the app)
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

## Current results
1,154 of 2,279 attendees (~51%) located confidently; about 90% of a manual sample was correct.
The rest are in `needs_review.csv` and shown as "not located yet". See `docs/LEARNING_GUIDE.md`
for how the numbers were obtained and what to improve next (seat-order window pass, bigger Whisper model).

## Deploy
Streamlit Community Cloud: repo `sumitverma77/convocation-finder`, branch `main`, main file `app.py`.
