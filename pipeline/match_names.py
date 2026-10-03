"""Fuzzy-match attendee names against ONE transcript.

How it works
  1. build_transcript(): Whisper transcript with the Urdu-script windows replaced by transcript_fix.txt;
     non-Latin / empty lines dropped.
  2. make_chunks(): every comma/period separated piece of a line is one "chunk" (usually one announced name).
  3. Scorer: for every attendee and chunk, score the two best name tokens (RapidFuzz, per word), so a short
     announced name ("Gurlin Kaur") still matches the long official one.
  4. first_pass(): greedy one-to-one assignment (a chunk belongs to one student) + top-5 candidates each.
  5. window_candidates(): relaxed search inside a time window (used with the branch/seat prior).

Run alone (Whisper only):  python -m pipeline.match_names
Normally use:              python -m pipeline.combine_results
"""
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from rapidfuzz.process import cdist

from pipeline import config

ATTENDEES_CSV = config.ATTENDEES_CSV
TRANSCRIPT_FILE = config.TRANSCRIPT_WHISPER
FIX_FILE = config.TRANSCRIPT_FIX
FIX_WINDOWS = config.FIX_WINDOWS   # minutes replaced by FIX_FILE
CLEAN_TRANSCRIPT = config.TRANSCRIPT_CLEAN

CONFIDENT = 90           # average score of the two best tokens
MIN_WEAK_CONFIDENT = 80  # and the weaker of those two tokens must be at least this
MIN_TOKEN = 72           # first pass: each of the two best tokens must reach this
ONE_NAME_MIN_LEN = 6      # one-name fallback: token at least this long ...
ONE_NAME_MIN_SIM = 88      # ... matching this well ...
ONE_NAME_CAP = 78          # ... can never score above this (stays "possible")
COMMON_TOKEN_COUNT = 25  # a name token shared by this many attendees is "common"
RELAXED_TOKEN = 62       # window pass: lower bar, because the time window already narrows it down
RELAXED_SCORE = 70
ZONE_START_MIN = 145     # name-calling starts after the speeches
MAX_CHUNK_WORDS = 7      # a real announced name is short; long chunks are speech
STOP = {"MR", "MS", "DR", "THE", "AND", "OF", "NEXT", "PLEASE", "STUDENT", "STUDENTS"}

LINE_RE = re.compile(r"^\[(\d+):(\d+)\]\s*(.*)$")


def read_lines(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.match(line.strip())
            if m:
                out.append((int(m.group(1)) * 60 + int(m.group(2)), m.group(3)))
    return out


def clean_lines(lines):
    """Drop non-Latin (Urdu/Hindi script) garbage and lines with no letters."""
    out = []
    for t, text in lines:
        if re.search(r"[^\x00-ɏ]", text):
            continue
        if len(re.sub(r"[^A-Za-z]", "", text)) < 3:
            continue
        out.append((t, text))
    return out


def build_transcript(fix_file=None, write=True):
    """Whisper transcript with the broken windows replaced by a repaired pass (fix_file, default transcript_fix.txt).
    Whisper is not deterministic, so a second repaired sample (transcript_fix_b.txt) can be used as extra evidence."""
    lines = read_lines(TRANSCRIPT_FILE)
    try:
        fix = read_lines(fix_file or FIX_FILE)
    except FileNotFoundError:
        fix = []
    if fix:
        def in_window(t):
            return any(a * 60 <= t < b * 60 for a, b in FIX_WINDOWS)
        lines = [x for x in lines if not in_window(x[0])] + fix
    lines.sort(key=lambda x: x[0])
    clean = clean_lines(lines)
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
    """DataFrame with at least: name, branch, order (PDF order). Works with the old one-column CSV too."""
    df = pd.read_csv(ATTENDEES_CSV)
    if "name" not in df.columns:
        df["name"] = df["Name"]
    if "branch" not in df.columns:
        df["branch"] = ""
    df["name"] = df["name"].astype(str).str.strip().str.upper()
    df = df[~df["name"].isin({"", "NAN", "RANK HOLDERS", "STAR STUDENTS", "RESERVED"})]
    df = df.drop_duplicates(subset=[c for c in ("reg_no", "name") if c in df.columns], keep="first")
    return df.reset_index(drop=True)


class Scorer:
    """Scores every (student, chunk) pair for one transcript."""

    def __init__(self, lines, attendees):
        self.chunks = make_chunks(lines)
        self.times = np.array([c[0] for c in self.chunks])
        flat_words, offsets = [], []
        for _, _, w in self.chunks:
            offsets.append(len(flat_words))
            flat_words.extend(w)
        offsets = np.array(offsets)

        self.tok_index, tokens = {}, []
        self.student_tokens = []
        freq = {}
        for n in attendees["name"]:
            toks = [t for t in re.findall(r"[A-Z]+", n) if len(t) >= 2]
            self.student_tokens.append(toks)
            for t in toks:
                freq[t] = freq.get(t, 0) + 1
                if t not in self.tok_index:
                    self.tok_index[t] = len(tokens)
                    tokens.append(t)
        # very common tokens (KUMAR, SINGH, SHARMA ...) say little about *who* was called
        self.tokens = tokens
        self.common = {self.tok_index[t] for t, c in freq.items() if c >= COMMON_TOKEN_COUNT}
        S = np.maximum(
            cdist(tokens, flat_words, scorer=fuzz.ratio, dtype=np.float32, workers=-1),
            cdist(tokens, flat_words, scorer=JaroWinkler.similarity, dtype=np.float32, workers=-1) * 100,
        )
        # a spoken word much shorter than the name token ("my" vs MAYANK) is not real evidence: scale it down
        lt = np.array([len(t) for t in tokens], dtype=np.float32)[:, None]
        lw = np.array([len(w) for w in flat_words], dtype=np.float32)[None, :]
        S = S * np.minimum(1.0, (lw + 1) / (0.7 * lt))
        self.S = S                                                # tokens x words
        self.offsets = offsets
        self.lens = np.array([len(c[2]) for c in self.chunks])
        self.M = np.maximum.reduceat(self.S, offsets, axis=1)     # tokens x chunks (best word per token)

    def _exact(self, tidx, ci):
        """Exact (score, weak) of a student against chunk ci: the two best tokens must match DIFFERENT words."""
        o = self.offsets[ci]
        sub = self.S[tidx, o:o + self.lens[ci]]                   # k tokens x m words
        if len(tidx) == 1 or sub.shape[1] == 1:
            best = float(sub.max())
            return best * 0.8, best                               # one usable word: cannot confirm two tokens
        best_avg, best_weak = 0.0, 0.0
        has_rare = any(t not in self.common for t in tidx)
        for a in range(len(tidx)):
            for b in range(a + 1, len(tidx)):
                if has_rare and tidx[a] in self.common and tidx[b] in self.common:
                    continue                                      # two surnames alone must not identify a student
                tot = sub[a][:, None] + sub[b][None, :]
                np.fill_diagonal(tot[: min(tot.shape)], -1)       # same word for both tokens is not allowed
                i, j = np.unravel_index(int(tot.argmax()), tot.shape)
                avg = tot[i, j] / 2
                if avg > best_avg:
                    best_avg, best_weak = float(avg), float(min(sub[a, i], sub[b, j]))
        # Surname garbled but a long, uncommon first name matches almost perfectly (e.g. "Shambhabi teach her" for
        # SHAMBHAVI JHA): keep it as a weak candidate. Capped below the confident level, so it is only ever "possible".
        rare = [k for k, t in enumerate(tidx) if t not in self.common and len(self.tokens[t]) >= ONE_NAME_MIN_LEN]
        if rare:
            top = float(max(sub[k].max() for k in rare))
            if top >= ONE_NAME_MIN_SIM and min(ONE_NAME_CAP, 0.85 * top) > best_avg:
                return min(ONE_NAME_CAP, 0.85 * top), top
        return best_avg, best_weak

    def student_scores(self, si, restrict=None, top=30):
        """(score per chunk, weak per chunk) for student si, exact on the `top` most promising chunks, 0 elsewhere.
        restrict: optional array of chunk indexes to consider."""
        toks = self.student_tokens[si]
        if not toks:
            return None, None
        tidx = [self.tok_index[t] for t in toks]
        rows = self.M[tidx]
        pre = rows[0] * 0.8 if len(toks) == 1 else np.sort(rows, axis=0)[-2:].mean(axis=0)
        cand = np.arange(len(pre)) if restrict is None else restrict
        if len(cand) == 0:
            return np.zeros(len(pre)), np.zeros(len(pre))
        cand = cand[np.argsort(pre[cand])[-top:]]
        score, weak = np.zeros(len(pre)), np.zeros(len(pre))
        for ci in cand:
            score[ci], weak[ci] = self._exact(tidx, ci)
        return score, weak

    def first_pass(self, n_students):
        """Greedy one-to-one assignment. Returns (assigned, candidates).
        assigned:   {si: (score, seconds, text, weak)}
        candidates: {si: [(score, seconds, text, weak), ... up to 5 best]}"""
        cand, per_student = [], {}
        for si in range(n_students):
            score, weak = self.student_scores(si)
            if score is None:
                continue
            ok = np.where(weak >= MIN_TOKEN)[0]
            if len(ok) == 0:
                continue
            best = ok[np.argsort(score[ok])[-5:]][::-1]
            per_student[si] = [(float(score[c]), int(self.times[c]), self.chunks[c][1], float(weak[c])) for c in best]
            for c in best:
                cand.append((float(score[c]), si, int(c), float(weak[c])))
        cand.sort(reverse=True)
        used_s, used_c, assigned = set(), set(), {}
        for score, si, ci, weak in cand:
            if si in used_s or ci in used_c:
                continue
            used_s.add(si)
            used_c.add(ci)
            assigned[si] = (score, int(self.times[ci]), self.chunks[ci][1], weak)
        return assigned, per_student

    def window_candidates(self, si, lo, hi, k=3):
        """Relaxed top-k candidates for student si among chunks with lo <= time <= hi (seconds)."""
        inwin = np.where((self.times >= lo) & (self.times <= hi))[0]
        score, weak = self.student_scores(si, restrict=inwin)
        if score is None:
            return []
        idx = np.where((self.times >= lo) & (self.times <= hi) & (weak >= RELAXED_TOKEN) & (score >= RELAXED_SCORE))[0]
        best = idx[np.argsort(score[idx])[-k:]][::-1]
        return [(float(score[c]), int(self.times[c]), self.chunks[c][1], float(weak[c])) for c in best]


def match(lines=None, write=False):
    """Simple API (used by tests and standalone runs): {official name: (score, seconds, text, weak)}."""
    if lines is None:
        lines = build_transcript()
    att = load_attendees()
    scorer = Scorer(lines, att)
    assigned, _ = scorer.first_pass(len(att))
    return {att["name"][si]: r for si, r in assigned.items()}


if __name__ == "__main__":
    res = match()
    ok = {n: r for n, r in res.items() if r[0] >= CONFIDENT and r[3] >= MIN_WEAK_CONFIDENT}
    print(f"matched: {len(res)}, confident: {len(ok)}")
