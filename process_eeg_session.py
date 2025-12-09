'''processes checker/input/sessions.xlsx:
- Reads second sheet (first row is header)
- Pads site_F11 to 3 digits
- Outputs to checker/input/sessions.csv
'''

import csv
import os
import pandas as pd
import numpy as np
from process_eeg_metadata import convert_to_int

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "eeg_metadata.xlsx")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "eeg_metadata.csv")

# Paths for sessions.xlsx
SESSIONS_INPUT_FILE = os.path.join(SCRIPT_DIR, "checker", "input", "sessions.xlsx")
SESSIONS_OUTPUT_CSV = os.path.join(SCRIPT_DIR, "checker", "input", "sessions.csv")


def pad_site_f11(val):
    """Pad site_F11 to 3 digits: <10 gets 00X, >=10 gets 0XX"""
    if pd.isna(val):
        return val
    try:
        num = int(float(val))
        return f"{num:03d}"
    except (ValueError, TypeError):
        return val


def process_sessions_xlsx():
    """Process checker/input/sessions.xlsx - read second sheet, pad site_F11, output to CSV."""

    print("\n" + "=" * 80)
    print("Processing sessions.xlsx")
    print("=" * 80)

    # Read second sheet (index 1) with first row as header
    df = pd.read_excel(SESSIONS_INPUT_FILE, sheet_name=1, header=0)

    print(f"Loaded {len(df)} data rows from Excel (second sheet)")
    print(f"Columns: {list(df.columns)}")

    # Filter: EEG upload status == "uploaded" or "needs annotations" AND F11EEG == "eeg"
    mask_uploaded = (df['EEG upload status'] == 'uploaded') | (df['EEG upload status'] == 'needs annotations')
    mask_eeg = df['F11EEG'] == 'eeg'
    df = df[mask_uploaded & mask_eeg]

    print(f"\nChecking {len(df)} rows where EEG upload status='uploaded' and F11EEG='eeg'")


    # Pad site_F11 to 3 digits if column exists
    if 'site_F11' in df.columns:
        df['site_F11'] = df['site_F11'].apply(pad_site_f11)
        print("Padded site_F11 column to 3 digits (e.g., 1 -> 001, 12 -> 012)")
    else:
        print("Warning: 'site_F11' column not found in sessions.xlsx")

    # Save to CSV
    df.to_csv(SESSIONS_OUTPUT_CSV, index=False, encoding='utf-8-sig')

    print(f"\nCSV saved to: {SESSIONS_OUTPUT_CSV}")
    print(f"   Total rows: {len(df)}")

    return {
        "output_file": SESSIONS_OUTPUT_CSV,
        "total_rows": len(df)
    }


if __name__ == "__main__":
    process_sessions_xlsx()
    print("\nScript completed.")
