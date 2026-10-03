"""Match official attendee names to the Whisper transcript and find when each is called.

Pipeline
  1. Build a clean transcript: original transcript.txt, with the Urdu-script windows replaced by
     transcript_fix.txt (forced-English re-run) if it exists. Non-Latin / empty lines are dropped.
  2. Split every transcript line into "chunks" (comma / full-stop separated pieces) - one chunk is
     usually one student name as the announcer says it.
  3. For each attendee, score every chunk with the best two name-tokens (fuzzy, per word), so a
     short announced name ("Gurlin Kaur") still matches the long official one.
  4. Greedy one-to-one assignment: a chunk can only belong to one student, a student gets one chunk.
  5. Write matched_timestamps.csv (confident) and needs_review.csv (the rest).

Run: python match_names.py
"""
import re
import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from rapidfuzz.process import cdist

ATTENDEES_CSV = "attendees.csv"
NAME_COLUMN = "Name"
TRANSCRIPT_FILE = "transcript_original_backup.txt"
FIX_FILE = "transcript_fix.txt"
FIX_WINDOWS = [(145, 185), (238, 280)]   # minutes replaced by FIX_FILE
OUT_OK = "matched_timestamps.csv"
OUT_REVIEW = "needs_review.csv"
CLEAN_TRANSCRIPT = "transcript_clean.txt"

CONFIDENT = 90        # average score of the two best tokens
MIN_WEAK_CONFIDENT = 80  # and the weaker of those two tokens must be at least this
MIN_TOKEN = 72        # each of the two best tokens must reach this
ZONE_START_MIN = 145  # name-calling starts after the speeches
MAX_CHUNK_WORDS = 7   # a real announced name is short; long chunks are speech
NON_NAMES = {"RANK HOLDERS", "STAR STUDENTS", "RESERVED"}
STOP = {"MR", "MS", "DR", "THE", "AND", "OF", "KUMAR_", "NEXT", "PLEASE", "STUDENT", "STUDENTS"}

LINE_RE = re.compile(r"^\[(\d+):(\d+)\]\s*(.*)$")


def read_lines(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.match(line.strip())
            if m:
                out.append((int(m.group(1)) * 60 + int(m.group(2)), m.group(3)))
    return out


def build_transcript():
    lines = read_lines(TRANSCRIPT_FILE)
    try:
        fix = read_lines(FIX_FILE)
    except FileNotFoundError:
        fix = []
    if fix:
        def in_window(t):
            return any(a * 60 <= t < b * 60 for a, b in FIX_WINDOWS)
        lines = [x for x in lines if not in_window(x[0])] + fix
    lines.sort(key=lambda x: x[0])
    clean = []
    for t, text in lines:
        if re.search(r"[^\x00-ɏ]", text):        # non-Latin (Urdu/Hindi script) garbage
            continue
        if len(re.sub(r"[^A-Za-z]", "", text)) < 3:   # "." and empty noise
            continue
        clean.append((t, text))
    with open(CLEAN_TRANSCRIPT, "w", encoding="utf-8") as f:
        for t, text in clean:
            f.write(f"[{t // 60:02d}:{t % 60:02d}] {text}\n")
    return clean


def words_of(text):
    return [w for w in re.findall(r"[A-Za-z]+", text.upper()) if len(w) >= 2 and w not in STOP]


def make_chunks(lines):
    """One chunk per comma/period-separated piece. Returns list of (seconds, text, words)."""
    chunks = []
    for t, text in lines:
        if t < ZONE_START_MIN * 60:
            continue
        for piece in re.split(r"[,.;]| and ", text):
            w = words_of(piece)
            if w and len(w) <= MAX_CHUNK_WORDS:
                chunks.append((t, piece.strip(), w))
    return chunks


def load_attendees():
    df = pd.read_csv(ATTENDEES_CSV)
    names = [str(n).strip().upper() for n in df[NAME_COLUMN] if str(n).strip().upper() not in NON_NAMES]
    seen, out = set(), []
    for n in names:
        if n and n != "NAN" and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def match():
    lines = build_transcript()
    chunks = make_chunks(lines)
    print(f"transcript lines kept: {len(lines)}, name chunks: {len(chunks)}")

    # flatten all chunk words so one matrix call scores every (student token, word)
    flat_words, offsets = [], []
    for _, _, w in chunks:
        offsets.append(len(flat_words))
        flat_words.extend(w)
    offsets = np.array(offsets)

    names = load_attendees()
    print(f"attendees: {len(names)}")

    # unique student tokens
    tok_index, tokens = {}, []
    student_tokens = []
    for n in names:
        toks = [t for t in re.findall(r"[A-Z]+", n) if len(t) >= 2]
        student_tokens.append(toks)
        for t in toks:
            if t not in tok_index:
                tok_index[t] = len(tokens)
                tokens.append(t)

    print("scoring (this takes a minute)...")
    S = np.maximum(
        cdist(tokens, flat_words, scorer=fuzz.ratio, dtype=np.float32, workers=-1),
        cdist(tokens, flat_words, scorer=JaroWinkler.similarity, dtype=np.float32, workers=-1) * 100,
    )                                                                          # tokens x words
    # best word similarity per (token, chunk)
    M = np.maximum.reduceat(S, offsets, axis=1)                                # tokens x chunks

    cand = []   # (score, student_idx, chunk_idx, weakest_token_score)
    for si, toks in enumerate(student_tokens):
        if not toks:
            continue
        rows = M[[tok_index[t] for t in toks]]                  # k x chunks
        if len(toks) == 1:
            score = rows[0] * 0.8
            weakest = rows[0]
        else:
            top2 = np.sort(rows, axis=0)[-2:]                   # two best tokens per chunk
            score = top2.mean(axis=0)
            weakest = top2[0]
        ok = np.where(weakest >= MIN_TOKEN)[0]
        if len(ok) == 0:
            continue
        best = ok[np.argsort(score[ok])[-5:]]
        for ci in best:
            cand.append((float(score[ci]), si, int(ci), float(weakest[ci])))

    cand.sort(reverse=True)
    used_student, used_chunk, results = set(), set(), {}
    for score, si, ci, weak in cand:
        if si in used_student or ci in used_chunk:
            continue
        used_student.add(si)
        used_chunk.add(ci)
        t, text, _ = chunks[ci]
        results[si] = (score, t, text, weak)

    rows_ok, rows_review = [], []
    for si, n in enumerate(names):
        if si in results:
            score, t, text, weak = results[si]
            row = {
                "Official Name": n,
                "Seconds": max(t - 2, 0),
                "Timestamp": f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}",
                "What the AI Heard": text,
                "Match Confidence %": round(score),
            }
            (rows_ok if score >= CONFIDENT and weak >= MIN_WEAK_CONFIDENT else rows_review).append(row)
        else:
            rows_review.append({"Official Name": n, "Seconds": "", "Timestamp": "",
                                "What the AI Heard": "", "Match Confidence %": 0})

    pd.DataFrame(rows_ok).to_csv(OUT_OK, index=False)
    pd.DataFrame(rows_review).to_csv(OUT_REVIEW, index=False)
    print(f"confident: {len(rows_ok)}  needs review: {len(rows_review)}  total: {len(names)}")


if __name__ == "__main__":
    match()
