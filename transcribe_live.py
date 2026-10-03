import subprocess
import sys
import os
from faster_whisper import WhisperModel

YOUTUBE_URL = "https://www.youtube.com/watch?v=iZuGjFTKXL8"
AUDIO_FILE = "livestream_audio.m4a"

def download_audio():
    print("Starting download from the BEGINNING of the livestream...")
    print("IMPORTANT: If it gets stuck downloading forever, press Ctrl+C in this terminal to stop downloading.")
    print("After you press Ctrl+C, it will automatically start transcribing what it downloaded.\n")
    
    command = [
        "yt-dlp",
        "--live-from-start",
        "-f", "bestaudio",
        "-o", AUDIO_FILE,
        YOUTUBE_URL
    ]
    
    try:
        subprocess.run(command, check=True)
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user. Moving on to transcription...\n")
    except subprocess.CalledProcessError:
        print("\n\nyt-dlp finished or encountered an error (stream might have ended). Moving on to transcription...\n")

def transcribe_audio():
    if not os.path.exists(AUDIO_FILE):
        print(f"Error: {AUDIO_FILE} was not found. Download might have failed.")
        sys.exit(1)

    print("Loading faster-whisper model (using 'base' model for speed)...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    print("Transcribing audio... (this might take a while depending on the length)")
    segments, info = model.transcribe(AUDIO_FILE, beam_size=5)
    
    with open("transcript.txt", "w", encoding="utf-8") as f:
        for segment in segments:
            start_mins = int(segment.start // 60)
            start_secs = int(segment.start % 60)
            timestamp = f"[{start_mins:02d}:{start_secs:02d}]"
            
            line = f"{timestamp} {segment.text}"
            print(line)
            f.write(line + "\n")
            
    print("\nTranscription complete! Saved to 'transcript.txt'.")

if __name__ == "__main__":
    download_audio()
    transcribe_audio()
