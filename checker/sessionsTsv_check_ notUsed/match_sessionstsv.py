'''
1) Assume there are sub-<patient_id>_sessions.tsv files stored flatly in checker/output/sessionsTsv_check/sessionstsv_downloaded/
2) Loop through each sessions.tsv, extract the <patient_id> from the filename.
    Match the <patient_id> to the corresponding PID1 column in checker/input/sessions.csv
3) Then within the sessions.tsv, extract the visit_time from session_id column (in the format of ses-visit<visit_time>m)
    Match the visit_time to the corresponding "Visit from MOP" column in checker/input/sessions.csv
4) If both patient_id and visit_time match, compare the rest of the columns in sessions.tsv to the corresponding columns in sessions.csv
    "session_description" should be matched to "Sessions.tsv description"; "subject_age_months" to "age_eeg_calc"; "sleep_captured" to "F11SLEEP"; "head_circumference" to "head_circumference" in respective _sessions.tsv and the sessions.csv
    Notice that the many *_sessions.tsv file do not have the head_circumference column, in that case, add the corresponding value from sessions.csv as a new column to the _sessions.tsv file
5) If any mismatch is found (excluding head_circumference), update the _sessions.tsv file to match the sessions.csv value and report it in terminal (patient-id and visit-time)
6) Save all the matched and updated _sessions.tsv files to checker/output/sessionsTsv_check/sessionstsv_matched/
'''

import os
import re
import glob
import pandas as pd

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)
SESSIONS_CSV = os.path.join(CHECKER_DIR, "input", "sessions.csv")
TSV_INPUT_DIR = os.path.join(CHECKER_DIR, "output", "sessionsTsv_check", "sessionstsv_downloaded")
TSV_OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "sessionsTsv_check", "sessionstsv_matched")

# Column mappings: sessions.tsv column -> sessions.csv column
COLUMN_MAPPINGS = {
    'session_description': 'Sessions.tsv description',
    'subject_age_months': 'age_eeg_calc',
    'sleep_captured': 'F11SLEEP',
    'head_circumference': 'head_circumference'
}


def extract_patient_id_from_filename(filename):
    """Extract patient_id from filename like 'sub-<patient_id>_sessions.tsv'"""
    match = re.match(r'sub-(.+)_sessions\.tsv', filename)
    if match:
        return match.group(1)
    return None


def extract_visit_time_from_session_id(session_id):
    """Extract visit_time from session_id like 'ses-visit<visit_time>m'"""
    match = re.search(r'ses-visit([\d.]+)m', str(session_id))
    if match:
        return float(match.group(1))
    return None


def normalize_value(val):
    """Normalize value for comparison (handle NaN, floats, strings)"""
    if pd.isna(val):
        return None
    if isinstance(val, float):
        # Convert to int if it's a whole number
        if val == int(val):
            return int(val)
        return val
    return str(val).strip()


def match_sessions():
    """Main function to match and update sessions.tsv files."""

    print("=" * 80)
    print("Matching sessions.tsv files to sessions.csv")
    print("=" * 80)

    # Create output directory if it doesn't exist
    os.makedirs(TSV_OUTPUT_DIR, exist_ok=True)

    # Load sessions.csv
    if not os.path.exists(SESSIONS_CSV):
        print(f"Error: sessions.csv not found at {SESSIONS_CSV}")
        return

    sessions_df = pd.read_csv(SESSIONS_CSV)
    print(f"Loaded sessions.csv with {len(sessions_df)} rows")
    print(f"Columns: {list(sessions_df.columns)}")

    # Get all tsv files
    tsv_files = glob.glob(os.path.join(TSV_INPUT_DIR, "sub-*_sessions.tsv"))

    if not tsv_files:
        print(f"\nNo sessions.tsv files found in {TSV_INPUT_DIR}")
        return

    print(f"\nFound {len(tsv_files)} sessions.tsv files to process")

    mismatches_found = []
    files_processed = 0
    files_updated = 0

    for tsv_path in tsv_files:
        filename = os.path.basename(tsv_path)
        patient_id = extract_patient_id_from_filename(filename)

        if not patient_id:
            print(f"Warning: Could not extract patient_id from {filename}")
            continue

        # Read the TSV file
        tsv_df = pd.read_csv(tsv_path, sep='\t')

        # Track if this file was updated
        file_updated = False

        # Check if head_circumference column exists, if not add it
        if 'head_circumference' not in tsv_df.columns:
            tsv_df['head_circumference'] = None

        # Process each row in the TSV
        for idx, row in tsv_df.iterrows():
            session_id = row.get('session_id', '')
            visit_time = extract_visit_time_from_session_id(session_id)

            if visit_time is None:
                continue

            # Find matching row in sessions.csv by PID1 and Visit from MOP
            matching_rows = sessions_df[
                (sessions_df['PID1'] == patient_id) &
                (sessions_df['Visit from MOP'] == visit_time)
            ]

            if matching_rows.empty:
                print(f"  No match found for patient_id={patient_id}, visit_time={visit_time}")
                continue

            csv_row = matching_rows.iloc[0]

            # Compare and update columns
            row_mismatches = []

            for tsv_col, csv_col in COLUMN_MAPPINGS.items():
                if tsv_col == 'head_circumference':
                    # Always add head_circumference from CSV (don't report as mismatch)
                    csv_val = csv_row.get(csv_col)
                    if not pd.isna(csv_val):
                        tsv_df.at[idx, tsv_col] = csv_val
                        file_updated = True
                else:
                    # Compare other columns
                    tsv_val = normalize_value(row.get(tsv_col))
                    csv_val = normalize_value(csv_row.get(csv_col))

                    if tsv_val != csv_val:
                        row_mismatches.append({
                            'column': tsv_col,
                            'tsv_value': tsv_val,
                            'csv_value': csv_val
                        })
                        # Update the TSV with CSV value
                        tsv_df.at[idx, tsv_col] = csv_row.get(csv_col)
                        file_updated = True

            if row_mismatches:
                mismatches_found.append({
                    'patient_id': patient_id,
                    'visit_time': visit_time,
                    'mismatches': row_mismatches
                })

        # Save the updated TSV file
        output_path = os.path.join(TSV_OUTPUT_DIR, filename)
        tsv_df.to_csv(output_path, sep='\t', index=False)
        files_processed += 1

        if file_updated:
            files_updated += 1

    # Report mismatches
    print("\n" + "=" * 80)
    print("MISMATCH REPORT")
    print("=" * 80)

    if mismatches_found:
        for item in mismatches_found:
            print(f"\n  Patient ID: {item['patient_id']}, Visit Time: {item['visit_time']}")
            for m in item['mismatches']:
                print(f"    - {m['column']}: TSV='{m['tsv_value']}' -> CSV='{m['csv_value']}'")

        print(f"\n\nTotal mismatches found: {len(mismatches_found)}")
    else:
        print("\n  No mismatches found (excluding head_circumference).")

    print(f"\n\nSummary:")
    print(f"  Files processed: {files_processed}")
    print(f"  Files updated: {files_updated}")
    print(f"  Output directory: {TSV_OUTPUT_DIR}")


if __name__ == "__main__":
    match_sessions()
    print("\nScript completed.")
