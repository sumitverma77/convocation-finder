"""Step 1: read the seating-number PDF -> data/interim/attendees.csv

One row per attendee, in the order of the PDF (S.No., which is the stage order):
  sno, branch, name, reg_no, seat_no          (plus Name = name, used by the matcher)

Run from the repo root: python -m pipeline.extract_attendees
"""
import re

import pandas as pd
import pdfplumber

from pipeline import config

REG = re.compile(r"\b\d{2}[A-Z]{3}\d{4,5}\b")
SEAT = re.compile(r"^[A-Z]{1,2}\d+(_\d+)?$")
SECTION_CODES = {"RH", "PHD", "STAR", "RESERVED"}


def clean(cell):
    return "" if cell is None else re.sub(r"\s+", " ", str(cell).replace("\n", " ")).strip()


def parse_row(cells):
    """Return a dict for a student row, or None if the row has no registration number."""
    reg = next((m.group(0) for c in cells if (m := REG.search(c))), None)
    if not reg:
        return None
    sno = next((c for c in cells if c.isdigit()), "")
    branch = re.sub(r"^\d{2}|\d+$", "", reg)           # 22BCE10104 -> BCE
    section = next((c for c in cells if c in SECTION_CODES or c == branch), branch)
    seat = next((c for c in cells if SEAT.match(c) and c != reg), "")
    name = ""
    for c in cells:
        if (not c or c == reg or c == section or c == branch or c in SECTION_CODES or c.isdigit()
                or SEAT.match(c) or REG.search(c) or re.match(r"^(Dr|Prof|Mr)\.?\s", c, re.I)
                or c.lower() in ("student name", "rank", "supervisor")):
            continue
        if re.search(r"[A-Za-z]{3}", c):
            name = c
            break
    name = re.sub(r"^(Mr|Ms|Mrs)\.?\s+", "", name, flags=re.I).strip()
    return {"sno": sno, "branch": section, "name": name.upper(), "reg_no": reg, "seat_no": seat}


def extract():
    rows = []
    with pdfplumber.open(config.SEATING_PDF) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    row = parse_row([clean(c) for c in r])
                    if row and row["name"]:
                        rows.append(row)
    df = pd.DataFrame(rows).drop_duplicates(subset="reg_no", keep="first").reset_index(drop=True)
    df["order"] = range(len(df))
    df["Name"] = df["name"]                      # column name the matcher expects
    df.to_csv(config.ATTENDEES_CSV, index=False)
    print(f"{len(df)} attendees -> {config.ATTENDEES_CSV}")
    print(df["branch"].value_counts().head(12).to_string())
    return df


if __name__ == "__main__":
    extract()
