'''
Process eeg_metadata.xlsx:
1) Convert first sheet to CSV
2) Pad site_F11 to 3 digits (001-009 for <10, 010-099 for >=10)
3) Pad "Visit from MOP" values <10 with one leading zero
4) Fix scheme column (Excel converts "10-20" to datetime)
5) Convert hardwarefilters_max to integer (e.g., 500.0 -> 500)
6) Flag sessions where uploaded PRV rows have empty required fields
'''

import csv
import os
import pandas as pd
import numpy as np

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "eeg_metadata.xlsx")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "eeg_metadata.csv")


def fix_scheme(val):
    """Fix scheme values that Excel converted from '10-20' to datetime."""
    if pd.isna(val):
        return val
    # If it's a datetime, convert back to "10-20"
    if isinstance(val, pd.Timestamp):
        # Excel interprets "10-20" as Oct 20, so convert back
        return "10-20"
    # If it's a string that looks like a date (e.g., "2025-10-20 00:00:00")
    val_str = str(val)
    if "10-20" in val_str or "10/20" in val_str:
        return "10-20"
    # Keep other values as-is (like "n/a", other scheme names)
    return val


def pad_site_f11(val):
    """Pad site_F11 to 3 digits: <10 gets 00X, >=10 gets 0XX"""
    if pd.isna(val):
        return val
    try:
        num = int(float(val))
        return f"{num:03d}"
    except (ValueError, TypeError):
        return val


def pad_visit_from_mop(val):
    """Pad Visit from MOP: <10 gets leading zero (e.g., 3 -> 03, 4.5 -> 04.5)"""
    if pd.isna(val):
        return val
    try:
        num = float(val)
        if num < 10:
            # Format with leading zero
            if num == int(num):
                return f"{int(num):02d}"
            else:
                # Handle decimals like 4.5 -> 04.5
                int_part = int(num)
                dec_part = str(num).split('.')[1]
                return f"{int_part:02d}.{dec_part}"
        else:
            # Leave values >= 10 as-is
            if num == int(num):
                return str(int(num))
            else:
                return str(num)
    except (ValueError, TypeError):
        return val


def convert_to_int(val):
    """Convert float values to integer (e.g., 500.0 -> 500)."""
    if pd.isna(val):
        return val
    try:
        num = float(val)
        # Check if it's a whole number
        if num == int(num):
            return str(int(num))
        else:
            return str(val)
    except (ValueError, TypeError):
        return val


def process_eeg_metadata():
    """Main function to process eeg_metadata.xlsx."""

    # Read Excel - keep first row (category headers) and use second row as actual headers
    # Read without any header first to preserve all rows
    df_raw = pd.read_excel(INPUT_FILE, sheet_name=0, header=None)

    # The second row (index 1) contains the actual column names we'll use for processing
    header_row = df_raw.iloc[1].tolist()

    # Create a working dataframe with second row as header (for data manipulation)
    # Force 'scheme' column to be read as string to prevent datetime conversion
    df = pd.read_excel(INPUT_FILE, sheet_name=0, header=1, dtype={'scheme': str})

    print(f"Loaded {len(df)} data rows from Excel")
    print(f"Columns: {list(df.columns)}")

    # ============================================
    # 1) Fix scheme column - convert datetime back to "10-20" format
    # ============================================
    df['scheme'] = df['scheme'].apply(fix_scheme)
    print("\nFixed 'scheme' column (converted datetime values back to '10-20')")

    # ============================================
    # 2) Pad site_F11 to 3 digits
    # ============================================
    df['site_F11'] = df['site_F11'].apply(pad_site_f11)
    print("Padded site_F11 column to 3 digits")

    # ============================================
    # 3) Pad "Visit from MOP" values <10 with one leading zero
    # ============================================
    df['Visit from MOP'] = df['Visit from MOP'].apply(pad_visit_from_mop)
    print("Padded 'Visit from MOP' column (values <10 get leading zero)")

    # ============================================
    # 4) Convert hardwarefilters_max to integer
    # ============================================
    df['hardwarefilters_max'] = df['hardwarefilters_max'].apply(convert_to_int)
    print("Converted 'hardwarefilters_max' to integer (e.g., 500.0 -> 500)")

    # ============================================
    # 5) Check for empty required fields in uploaded PRV rows
    # ============================================
    required_fields = [
        'scheme',
        'site_F11',
        'visit_id',
        'age_eeg_calc',
        'F11SYSTEM',
        'F11SLEEP',
        'session',
        'BIDS compliant EEG filename',
        'Visit Type',
        'ManufacturersModelName',
        'hardwarefilters_min',
        'hardwarefilters_max'
        'Headcircumference'
    ]

    # Filter: EEG upload status == "uploaded" AND FileName (Original) starts with "PRV"
    mask_uploaded = df['EEG upload status'] == 'uploaded'
    mask_prv = df['FileName (Original)'].astype(str).str.startswith('PRV')
    filtered_df = df[mask_uploaded & mask_prv]

    print(f"\nChecking {len(filtered_df)} rows where EEG upload status='uploaded' and FileName starts with 'PRV'")

    flagged_sessions = []

    for idx, row in filtered_df.iterrows():
        session_name = row.get('session', f'row_{idx}')
        pid = row.get('PID1', 'unknown')
        filename = row.get('FileName (Original)', 'unknown')

        empty_fields = []
        for field in required_fields:
            val = row.get(field)
            # Check if empty: NaN, None, empty string, or whitespace
            if pd.isna(val) or (isinstance(val, str) and val.strip() == ''):
                empty_fields.append(field)

        if empty_fields:
            flagged_sessions.append({
                'session': session_name,
                'PID1': pid,
                'FileName': filename,
                'empty_fields': empty_fields
            })

    # ============================================
    # Report flagged sessions
    # ============================================
    print("\n" + "=" * 80)
    print("FLAGGED SESSIONS (uploaded PRV rows with empty required fields)")
    print("=" * 80)

    if flagged_sessions:
        for item in flagged_sessions:
            print(f"\n  Session: {item['session']}")
            print(f"    PID1: {item['PID1']}")
            print(f"    FileName: {item['FileName']}")
            print(f"    Empty fields: {', '.join(item['empty_fields'])}")

        print(f"\n\nTotal flagged: {len(flagged_sessions)} sessions")
    else:
        print("\n  No sessions with empty required fields found.")

    # ============================================
    # Save to CSV (preserving the first row as category headers)
    # ============================================
    # Reconstruct the full dataframe with the category header row
    category_row = df_raw.iloc[0].tolist()

    # Create output: first row is categories, then data with column headers
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        # Write category row
        writer.writerow(category_row)

        # Write header row (column names)
        writer.writerow(df.columns.tolist())

        # Write data rows
        for idx, row in df.iterrows():
            writer.writerow(row.tolist())

    print(f"\n\nCSV saved to: {OUTPUT_CSV}")
    print(f"   Total rows (including both header rows): {len(df) + 2}")

    return {
        "output_file": OUTPUT_CSV,
        "total_rows": len(df),
        "flagged_sessions": flagged_sessions
    }


if __name__ == "__main__":
    process_eeg_metadata()
    print("\nScript completed.")
