import subprocess
import os
from faster_whisper import WhisperModel

AUDIO_FILE = r"C:\Users\ASUS\live_audio.m4a"
OUTPUT_FILE = r"C:\Users\ASUS\transcript.txt"

CHUNK_SECONDS = 300  # 5 minutes

print("Getting audio duration...")

result = subprocess.run(
    [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        AUDIO_FILE
    ],
    capture_output=True,
    text=True
)

duration = float(result.stdout.strip())

print(f"Audio length: {duration / 3600:.2f} hours")

total_chunks = int((duration + CHUNK_SECONDS - 1) // CHUNK_SECONDS)

print(f"Total chunks: {total_chunks}")
print("Loading Whisper model...")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded.")

# Start fresh
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

    for i in range(total_chunks):

        start = i * CHUNK_SECONDS
        remaining = duration - start
        chunk_duration = min(CHUNK_SECONDS, remaining)

        print(
            f"\nChunk {i + 1}/{total_chunks} "
            f"({start / 60:.1f} - {(start + chunk_duration) / 60:.1f} min)"
        )

        chunk_file = os.path.join(
            os.path.dirname(AUDIO_FILE),
            f"_chunk_{i}.wav"
        )

        # Extract only this 5-minute section
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss", str(start),
                "-i", AUDIO_FILE,
                "-t", str(chunk_duration),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                chunk_file
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        print("Transcribing...")

        segments, info = model.transcribe(
            chunk_file,
            beam_size=1,
            vad_filter=True
        )

        for segment in segments:

            timestamp = start + segment.start

            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)

            text = segment.text.strip()

            if text:
                line = f"[{minutes:02d}:{seconds:02d}] {text}"

                print(line)

                f.write(line + "\n")
                f.flush()

        os.remove(chunk_file)

        print(f"Finished chunk {i + 1}/{total_chunks}")

print("\nDONE!")
print(f"Transcript: {OUTPUT_FILE}")