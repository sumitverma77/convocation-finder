"""Run the matcher on BOTH transcripts (our Whisper one and YouTube's auto-captions), compare, and merge.

Rules per student
  * both transcripts find them within 90 s of each other  -> agreement: confident, best score + 5 bonus
  * only one transcript finds them                         -> confident only if score >= SINGLE_SOURCE_MIN
  * transcripts disagree (different place)                 -> goes to needs_review (best guess kept)
Writes matched_timestamps.csv, needs_review.csv, comparison_report.csv.

Run: python combine_results.py
"""
import pandas as pd
import match_names as mn

AGREE_SECONDS = 90
SINGLE_SOURCE_MIN = 93   # one transcript alone must be very sure


def read_lines(path):
    return mn.read_lines(path)


def clean(lines):
    return [(t, x) for t, x in lines if len(mn.re.sub(r"[^A-Za-z]", "", x)) >= 3]


print("== Whisper transcript ==")
whisper = mn.match(mn.build_transcript(), write=False)
print("== YouTube captions ==")
yt = mn.match(clean(read_lines("transcript_yt.txt")), write=False)

names = mn.load_attendees()


def is_confident(r):
    return r is not None and r[0] >= mn.CONFIDENT and r[3] >= mn.MIN_WEAK_CONFIDENT


ok, review, report = [], [], []
for n in names:
    w, y = whisper.get(n), yt.get(n)
    wc, yc = is_confident(w), is_confident(y)
    status, pick, score = "none", None, 0
    if w and y and abs(w[1] - y[1]) <= AGREE_SECONDS:
        status = "agree"
        pick = w if w[0] >= y[0] else y
        score = min(100, pick[0] + 5)
    elif wc and yc:
        status = "conflict"
        pick = w if w[0] >= y[0] else y
        score = pick[0]
    elif wc or yc:
        pick = w if wc else y
        score = pick[0]
        status = ("whisper_only" if wc else "youtube_only") if score >= SINGLE_SOURCE_MIN else "weak"
    elif w or y:
        status = "weak"
        pick = max([r for r in (w, y) if r], key=lambda r: r[0])
        score = pick[0]
    report.append({"Official Name": n, "status": status,
                   "whisper_sec": w[1] if w else "", "whisper_heard": w[2] if w else "", "whisper_score": round(w[0]) if w else "",
                   "yt_sec": y[1] if y else "", "yt_heard": y[2] if y else "", "yt_score": round(y[0]) if y else ""})
    if pick is None:
        review.append({"Official Name": n, "Seconds": "", "Timestamp": "", "What the AI Heard": "", "Match Confidence %": 0})
        continue
    t = pick[1]
    row = {"Official Name": n, "Seconds": max(t - 2, 0),
           "Timestamp": f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}",
           "What the AI Heard": pick[2], "Match Confidence %": round(score)}
    (ok if status in ("agree", "whisper_only", "youtube_only") else review).append(row)

pd.DataFrame(ok).to_csv(mn.OUT_OK, index=False)
pd.DataFrame(review).to_csv(mn.OUT_REVIEW, index=False)
rep = pd.DataFrame(report)
rep.to_csv("comparison_report.csv", index=False)
print("\n", rep["status"].value_counts().to_string())
print(f"\nconfident total: {len(ok)}  needs review: {len(review)}  of {len(names)}")
