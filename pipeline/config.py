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
TRANSCRIPT_YT = INTERIM / "transcript_yt.txt"
TRANSCRIPT_CLEAN = INTERIM / "transcript_clean.txt"
COMPARISON_REPORT = INTERIM / "comparison_report.csv"

# final
MATCHED_CSV = PROCESSED / "matched_timestamps.csv"
REVIEW_CSV = PROCESSED / "needs_review.csv"
