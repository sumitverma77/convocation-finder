"""Re-transcribe the time windows where Whisper auto-detected the wrong language
(Urdu script instead of English) by forcing language="en".

Output: data/interim/transcript_fix.txt with absolute [MM:SS] timestamps (same format as transcript.txt).
Step 3. Run from the repo root: python -m pipeline.retranscribe_windows
"""
import os
import subprocess

from faster_whisper import WhisperModel

from pipeline import config

AUDIO_FILE = str(config.AUDIO_FILE)
OUT_FILE = config.TRANSCRIPT_FIX
# (start_minute, end_minute) windows that contain Urdu-script garbage
WINDOWS = config.FIX_WINDOWS

model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=12)

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for start_min, end_min in WINDOWS:
        wav = str(config.INTERIM / f"_win_{start_min}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start_min * 60), "-t", str((end_min - start_min) * 60),
             "-i", AUDIO_FILE, "-vn", "-ac", "1", "-ar", "16000", wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
        segments, _ = model.transcribe(
            wav, language="en", beam_size=5, vad_filter=False, condition_on_previous_text=False,
            initial_prompt="Convocation ceremony. The announcer reads Indian student names, "
                           "programme and rank, for example: Gurleen Kaur Makhija, B.Tech Computer Science.",
        )
        for seg in segments:
            t = int(start_min * 60 + seg.start)
            text = seg.text.strip()
            if text:
                out.write(f"[{t // 60:02d}:{t % 60:02d}] {text}\n")
                out.flush()
        os.remove(wav)
        print(f"window {start_min}-{end_min} done", flush=True)
print("DONE", flush=True)
