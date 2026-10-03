"""Step 2: transcribe the full audio in 1-hour chunks (keeps RAM low) -> data/interim/transcript_whisper.txt

Run from the repo root: python -m pipeline.transcribe_audio [start_chunk]
(start_chunk > 0 appends, so a crashed run can resume.)
"""
import math
import os
import subprocess
import sys

from faster_whisper import WhisperModel

from pipeline import config

AUDIO_FILE = str(config.AUDIO_FILE)

def get_duration(filename):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return float(result.stdout.strip())

def split_and_transcribe(start_chunk=0):
    if not os.path.exists(AUDIO_FILE):
        print(f"Error: {AUDIO_FILE} not found!")
        return

    duration = get_duration(AUDIO_FILE)
    chunk_length = 3600 # 1 hour chunks (3600 seconds)
    num_chunks = math.ceil(duration / chunk_length)
    
    print(f"Total audio duration: {duration/3600:.2f} hours.")
    print(f"Splitting into {num_chunks} chunks to prevent your computer from running out of RAM...\n")
    
    print("Loading AI model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    with open(config.TRANSCRIPT_WHISPER, "w" if start_chunk == 0 else "a", encoding="utf-8") as f:
        for i in range(start_chunk, num_chunks):
            start_time = i * chunk_length
            chunk_file = str(config.INTERIM / f"_chunk_{i}.m4a")
            print(f"\n--- Extracting Audio Chunk {i+1} of {num_chunks} ---")
            
            # Use ffmpeg to cut a 1-hour chunk
            subprocess.run([
                "ffmpeg", "-y", "-i", AUDIO_FILE, 
                "-ss", str(start_time), "-t", str(chunk_length), 
                "-c", "copy", chunk_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"Transcribing Chunk {i+1}...")
            
            # Transcribe just this 1 hour
            segments, info = model.transcribe(chunk_file, beam_size=5, language="en")
            
            for segment in segments:
                # We must add the 1-hour offset back to the timestamp so the final times are correct!
                actual_start = segment.start + start_time
                start_mins = int(actual_start // 60)
                start_secs = int(actual_start % 60)
                timestamp = f"[{start_mins:02d}:{start_secs:02d}]"
                
                line = f"{timestamp} {segment.text}"
                try:
                    print(line.encode('ascii', 'ignore').decode('ascii'))
                except:
                    pass
                f.write(line + "\n")
            
            # Delete the temporary chunk to save hard drive space
            os.remove(chunk_file)
            
    print("\n✅ Successfully transcribed all 6+ hours of audio! Saved to transcript_whisper.txt.")

if __name__ == "__main__":
    split_and_transcribe(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
