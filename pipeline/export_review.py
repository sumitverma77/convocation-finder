"""Create the manual review sheet: data/manual/review_sheet.xlsx

One row per student we are NOT sure about (status possible / none), best candidates first, each with a link that
opens the video at that second. Fill the last column "your_answer" and save, then run
`python -m pipeline.combine_results` again.

your_answer can be:
  1 / 2 / 3     -> option 1, 2 or 3 is the right moment
  4:35:57       -> the right time (h:mm:ss or mm:ss) if none of the options is right
  x             -> not in the recording (absent / not called)
  (empty)       -> unknown, leave as is
Answers already written in an existing sheet are kept when the sheet is regenerated.

Run from the repo root: python -m pipeline.export_review
"""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from pipeline import config


def link(seconds, label):
    url = f"https://youtu.be/{config.VIDEO_ID}?t={int(seconds)}"
    return f'=HYPERLINK("{url}","▶ {label}")'


def main():
    res = pd.read_csv(config.RESULTS_CSV)
    cand = pd.read_csv(config.CANDIDATES_CSV)

    old = {}
    if config.REVIEW_SHEET.exists():
        ws_old = load_workbook(config.REVIEW_SHEET, data_only=True).active
        hdr = [c.value for c in ws_old[1]]
        if "your_answer" in hdr and "id" in hdr:
            i_id, i_ans = hdr.index("id"), hdr.index("your_answer")
            for row in ws_old.iter_rows(min_row=2, values_only=True):
                if row[i_ans] not in (None, ""):
                    old[int(row[i_id])] = row[i_ans]

    todo = res[res["status"].isin(["possible", "none"])].copy()
    best = cand[cand["rank"] == 1].set_index("id")["confidence"]
    todo["top"] = todo["id"].map(best).fillna(0)
    todo = todo.sort_values(["status", "top"], ascending=[True, False])   # possible first, strongest first

    wb = Workbook()
    ws = wb.active
    ws.title = "review"
    head = ["id", "name", "status"]
    for k in (1, 2, 3):
        head += [f"option{k} video", f"option{k} heard", f"option{k} %"]
    head += ["expected window", "your_answer"]
    ws.append(head)

    for _, r in todo.iterrows():
        mine = cand[cand["id"] == r["id"]].sort_values("rank")
        row = [int(r["id"]), r["name"], r["status"]]
        for k in range(3):
            if k < len(mine):
                c = mine.iloc[k]
                row += [link(c["seconds"], c["timestamp"]), c["heard"], int(c["confidence"])]
            else:
                row += ["", "", ""]
        if pd.notna(r["expected_from"]) and r["expected_from"] != "":
            row.append(link(r["expected_from"], f"{int(r['expected_from']) // 3600}:{int(r['expected_from']) % 3600 // 60:02d}"
                            f" to {int(r['expected_to']) // 3600}:{int(r['expected_to']) % 3600 // 60:02d}"))
        else:
            row.append("")
        row.append(old.get(int(r["id"]), ""))
        ws.append(row)

    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4F46E5")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    last = ws.max_column
    for r in range(2, ws.max_row + 1):
        ws.cell(r, last).fill = PatternFill("solid", fgColor="FEF9C3")
        for col in (4, 7, 10, last - 1):
            ws.cell(r, col).font = Font(color="0563C1", underline="single")
    widths = {"A": 6, "B": 28, "C": 10}
    for i in range(1, last + 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(get_column_letter(i), 16)
    for col in (5, 8, 11):
        ws.column_dimensions[get_column_letter(col)].width = 26
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions

    config.MANUAL.mkdir(parents=True, exist_ok=True)
    wb.save(config.REVIEW_SHEET)
    print(f"{len(todo)} students to review -> {config.REVIEW_SHEET}  (kept {len(old)} earlier answers)")


if __name__ == "__main__":
    main()
