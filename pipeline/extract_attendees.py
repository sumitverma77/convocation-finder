"""Step 1: pull attendee names out of the seating-number PDF -> data/interim/attendees.csv

Run from the repo root: python -m pipeline.extract_attendees
"""
import os

import pandas as pd
import pdfplumber

from pipeline import config

PDF_PATH = config.SEATING_PDF
OUTPUT_CSV = config.ATTENDEES_CSV

def extract_names_from_pdf():
    print(f"Reading PDF: {PDF_PATH}")
    all_names = []
    
    if not os.path.exists(PDF_PATH):
        print("Error: PDF not found at the specified path.")
        return

    with pdfplumber.open(PDF_PATH) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    row = [str(cell).strip().replace('\n', ' ') if cell else "" for cell in row]
                    for cell in row:
                        if cell == "Student Name" or cell == "Student_Name" or cell == "RESERVED":
                            continue
                        
                        if cell.isupper() and len(cell) > 4 and not any(char.isdigit() for char in cell):
                            if " " in cell or "." in cell:
                                clean_name = cell.strip()
                                if clean_name not in all_names:
                                    all_names.append(clean_name)

    print(f"Extracted {len(all_names)} unique names from the PDF!")
    
    df = pd.DataFrame({"Name": all_names})
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved names to {OUTPUT_CSV}")

if __name__ == "__main__":
    extract_names_from_pdf()
