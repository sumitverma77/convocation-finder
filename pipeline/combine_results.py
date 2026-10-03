"""Combine everything we know into per-student results.

Evidence used
  * Whisper transcript and YouTube auto-captions, each matched separately (pipeline.match_names)
  * agreement between the two transcripts
  * branch / seat-row prior: students of the same branch (and seat row) are called in the same part of the
    ceremony. From the confident matches we learn "BCE row A is called around 3h30" and use that as an expected
    time window to (a) penalise matches far outside it and (b) find weaker matches inside it.

Status per student
  confident  both transcripts agree, or one is very sure, and the time fits the branch
  possible   we have 1-3 candidate moments but are not sure (the app shows all of them with scores)
  none       nothing usable; the app shows the expected time window for the student's branch

Writes data/processed/results.csv (one row per student) and candidates.csv (top 3 per student).
Privacy: the attendee list was shared internally, so branch / registration number are never written to these
published files; they are only used in memory to compute the expected time window.
Run from the repo root: python -m pipeline.combine_results
"""
import numpy as np
import pandas as pd

from pipeline import config
from pipeline import match_names as mn

AGREE_SECONDS = 90
CLUSTER_SECONDS = 60       # candidates closer than this are the same moment
SINGLE_SOURCE_MIN = 93     # one transcript alone must be very sure ...
SINGLE_IN_WINDOW_MIN = 88  # ... or a bit less sure if the time fits the expected window and no other student competes
MARGIN = 4                 # best student for a spoken name must beat the runner-up by this much
BOTH_SOURCES_MIN = 80
WINDOW = 45 * 60           # half-width of the expected-time window
FAR = 2 * WINDOW           # beyond this from the expected time, a match is suspicious
OUTLIER = 120 * 60         # anchors this far from their branch median are ignored when learning the prior
MIN_GROUP = 3
POSSIBLE_MIN = 70


def hms(t):
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def seat_row(seat):
    s = "" if pd.isna(seat) else str(seat)
    return s[:1] if s else ""


def main():
    att = mn.load_attendees()
    n = len(att)
    att["row"] = att["seat_no"].map(seat_row) if "seat_no" in att.columns else ""
    ids = att["order"] if "order" in att.columns else pd.Series(range(n))

    print("== Whisper transcript ==")
    sc_w = mn.Scorer(mn.build_transcript(), att)
    asg_w, cand_w = sc_w.first_pass(n)
    print("== YouTube captions ==")
    sc_y = mn.Scorer(mn.clean_lines(mn.read_lines(config.TRANSCRIPT_YT)), att)
    asg_y, cand_y = sc_y.first_pass(n)

    # ---- learn the branch / seat-row prior from students both transcripts agree on
    anchors = {}
    for si in range(n):
        w, y = asg_w.get(si), asg_y.get(si)
        if w and y and abs(w[1] - y[1]) <= AGREE_SECONDS:
            anchors[si] = w[1]
    by_branch = {}
    for si, t in anchors.items():
        by_branch.setdefault(att["branch"][si], []).append(t)
    branch_med = {b: float(np.median(v)) for b, v in by_branch.items() if len(v) >= MIN_GROUP}
    good = {si: t for si, t in anchors.items()
            if att["branch"][si] in branch_med and abs(t - branch_med[att["branch"][si]]) <= OUTLIER}
    groups = {}
    for si, t in good.items():
        groups.setdefault((att["branch"][si], att["row"][si]), {})[si] = t
        groups.setdefault((att["branch"][si], None), {})[si] = t

    def expected(si):
        """Expected call time (seconds) from other students of the same branch+row, else branch; None if unknown."""
        for key in ((att["branch"][si], att["row"][si]), (att["branch"][si], None)):
            g = {k: v for k, v in groups.get(key, {}).items() if k != si}   # leave-one-out
            if len(g) >= MIN_GROUP:
                return float(np.median(list(g.values())))
        return None

    # who else is competing for the same spoken chunk? (source, second) -> scores of all students that list it
    competitors = {}
    for src, cands in (("whisper", cand_w), ("youtube", cand_y)):
        for si_, lst in cands.items():
            for c in lst:
                competitors.setdefault((src, c[1]), []).append((c[0], si_))

    def margin(si_, cl):
        """My score minus the best other student's score for the same spoken chunk (any source in the cluster)."""
        others = [sc for src in cl["sources"] for t_ in range(cl["t"] - 3, cl["t"] + 4)
                  for sc, s2 in competitors.get((src, t_), []) if s2 != si_]
        return cl["score"] - max(others) if others else 100.0

    results, candidates = [], []
    counts = {"confident": 0, "possible": 0, "none": 0}
    for si in range(n):
        exp = expected(si)
        items = []   # (score, t, text, weak, source, assigned)
        for src, cands, asg in (("whisper", cand_w, asg_w), ("youtube", cand_y, asg_y)):
            a = asg.get(si)
            for c in cands.get(si, []):
                items.append((*c, src, a is not None and a[1] == c[1]))
        if exp is not None:
            sc_pairs = (("whisper", sc_w, asg_w), ("youtube", sc_y, asg_y))
            for src, sc, asg in sc_pairs:
                for c in sc.window_candidates(si, exp - WINDOW, exp + WINDOW):
                    items.append((*c, src, False))

        clusters = []
        for it in sorted(items, key=lambda x: -x[0]):
            for cl in clusters:
                if abs(cl["t"] - it[1]) <= CLUSTER_SECONDS:
                    cl["sources"].add(it[4])
                    cl["assigned"] |= it[5]
                    break
            else:
                clusters.append({"t": it[1], "text": it[2], "score": it[0], "weak": it[3],
                                 "sources": {it[4]}, "assigned": it[5]})
        for cl in clusters:
            conf = min(100.0, cl["score"] + 5 * (len(cl["sources"]) - 1))
            d = abs(cl["t"] - exp) if exp is not None else None
            cl["in_window"] = d is not None and d <= WINDOW
            cl["far"] = d is not None and d > FAR
            cl["conf"] = conf
            cl["rank"] = conf + (8 if cl["in_window"] else 0) - (8 if (exp is not None and not cl["in_window"]) else 0) - (12 if cl["far"] else 0)
        clusters.sort(key=lambda c: -c["rank"])          # window-aware order, used to DECIDE the status
        top3 = clusters[:3]

        status = "none"
        if top3:
            c = top3[0]
            both = len(c["sources"]) == 2
            strong = ((both and c["score"] >= BOTH_SOURCES_MIN)
                      or (c["score"] >= SINGLE_SOURCE_MIN and c["weak"] >= mn.MIN_WEAK_CONFIDENT)
                      or (c["score"] >= SINGLE_IN_WINDOW_MIN and c["weak"] >= mn.MIN_WEAK_CONFIDENT
                          and c["in_window"] and margin(si, c) >= MARGIN))
            if c["assigned"] and strong and not c["far"]:
                status = "confident"
            elif c["conf"] >= POSSIBLE_MIN:
                status = "possible"
        counts[status] += 1
        # DISPLAY order: a confident answer stays first; when we are unsure, show the highest confidence first
        if status == "confident":
            top3 = [top3[0]] + sorted(clusters[1:], key=lambda c: (-c["conf"], not c["in_window"]))[:2]
        else:
            top3 = sorted(clusters, key=lambda c: (-c["conf"], not c["in_window"]))[:3]

        # NOTE: branch is used internally for the time prior but is deliberately NOT written to the published CSVs
        row = {"id": int(ids[si]), "name": att["name"][si], "status": status,
               "expected_from": int(max(exp - WINDOW, 0)) if exp is not None else "",
               "expected_to": int(exp + WINDOW) if exp is not None else ""}
        if top3 and status != "none":
            c = top3[0]
            row.update({"seconds": max(c["t"] - 3, 0), "timestamp": hms(c["t"]), "heard": c["text"],
                        "confidence": round(c["conf"])})
        results.append(row)
        if status != "none":
            for r, c in enumerate(top3, 1):
                candidates.append({"id": int(ids[si]), "rank": r, "seconds": max(c["t"] - 3, 0),
                                   "timestamp": hms(c["t"]), "heard": c["text"], "confidence": round(c["conf"]),
                                   "sources": "+".join(sorted(c["sources"])), "in_window": bool(c["in_window"])})

    res = pd.DataFrame(results)
    cand = pd.DataFrame(candidates)
    res.to_csv(config.RESULTS_CSV, index=False)
    cand.to_csv(config.CANDIDATES_CSV, index=False)
    print("\nstatus counts:", counts, "of", n)
    print("branches with a learned time prior:", len(branch_med), "| anchors used:", len(good))


if __name__ == "__main__":
    main()
