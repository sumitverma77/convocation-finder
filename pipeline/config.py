"""Single place for every file path used by the pipeline and the app."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"              # big/source files, git-ignored
INTERIM = ROOT / "data" / "interim"      # intermediate files, git-ignored
PROCESSED = ROOT / "data" / "processed"  # final results, committed (the app reads these)

VIDEO_ID = "iZuGjFTKXL8"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

# raw inputs
AUDIO_FILE = RAW / "livestream_audio.m4a"
SEATING_PDF = RAW / "SEATING_NUMBERS.pdf"
YT_CAPTIONS_VTT = RAW / "yt_captions.en-orig.vtt"

# interim
ATTENDEES_CSV = INTERIM / "attendees.csv"
TRANSCRIPT_WHISPER = INTERIM / "transcript_whisper.txt"
TRANSCRIPT_FIX = INTERIM / "transcript_fix.txt"
TRANSCRIPT_FIX_B = INTERIM / "transcript_fix_b.txt"   # an earlier, independent Whisper sample of the repaired windows
TRANSCRIPT_YT = INTERIM / "transcript_yt.txt"
TRANSCRIPT_CLEAN = INTERIM / "transcript_clean.txt"

# stretches (minutes) where Whisper auto-detected the wrong language and wrote Urdu script / dropped names;
# pipeline.retranscribe_windows redoes them in forced English and match_names swaps them in
FIX_WINDOWS = [(145, 185), (238, 282), (285, 300), (318, 360), (505, 535)]

# manual review (git-ignored): the sheet you fill in, plus the answers read back by combine_results
MANUAL = ROOT / "data" / "manual"
REVIEW_SHEET = MANUAL / "review_sheet.xlsx"
KNOWN_ANSWERS = MANUAL / "known_answers.csv"   # name,time rows typed by hand (any time, any student)

# final
RESULTS_CSV = PROCESSED / "results.csv"        # one row per student: status, best moment, expected window
CANDIDATES_CSV = PROCESSED / "candidates.csv"  # up to 3 candidate moments per student
