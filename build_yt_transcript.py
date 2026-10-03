"""Convert YouTube's rolling auto-captions (VTT) into the same "[MM:SS] text" format as transcript.txt.

Run: python build_yt_transcript.py   -> transcript_yt.txt
"""
import re

SRC = "yt_captions.en-orig.vtt"
OUT = "transcript_yt.txt"
CUE = re.compile(r"^(\d+):(\d+):(\d+)\.\d+ --> ")

lines, last = [], None
with open(SRC, encoding="utf-8") as f:
    block, start = [], None
    for raw in list(f) + ["\n"]:
        raw = raw.rstrip("\n")
        m = CUE.match(raw)
        if m:
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            block = []
        elif raw.strip() == "":
            text = [re.sub(r"<[^>]+>", "", t).strip() for t in block]
            text = [t for t in text if t]
            if start is not None and text and text[-1] != last:
                lines.append((start, text[-1]))
                last = text[-1]
            block = []
        elif start is not None and not raw.startswith(("WEBVTT", "Kind:", "Language:")):
            block.append(raw)

with open(OUT, "w", encoding="utf-8") as f:
    for t, text in lines:
        f.write(f"[{t // 60:02d}:{t % 60:02d}] {text}\n")
print(len(lines), "caption lines ->", OUT)
