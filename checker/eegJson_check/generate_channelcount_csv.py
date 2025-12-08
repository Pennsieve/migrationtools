'''
Generate a CSV file with channel counts from aligned eeg.json files.

Logic:
1. Iterate all *_eeg.json files in eegjson_aligned/
2. Extract patient-id and session_dir from the path
3. Read the channel counts from the eeg.json file
4. Output to checker/input/channelCountChecker_final.csv
'''

import csv
import json
import os
from pathlib import Path

# Paths relative to checker directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)

# Input: aligned JSON files
INPUT_DIR = os.path.join(CHECKER_DIR, "output", "eegJson_check", "eegjson_aligned")
# Output: CSV file
OUTPUT_CSV = os.path.join(CHECKER_DIR, "input", "channelCountChecker_final.csv")

DRY_RUN = False  # True = print actions only, no file writes


def extract_patient_session_from_path(filepath: Path):
    """
    Extract patient_id and session_dir from file path.
    e.g., .../sub-13UL/ses-visit03m/sub-13UL_ses-visit03m_task-prv_eeg.json
    Returns (patient_id, session_dir) where patient_id includes 'sub-' prefix
    """
    parts = filepath.parts

    patient_id = None
    session_dir = None

    for part in parts:
        if part.startswith('sub-'):
            patient_id = part[:8]  # Keep 'sub-XXXX' format (8 chars)
        elif part.startswith('ses-'):
            session_dir = part

    return patient_id, session_dir


def read_channel_counts(json_path: Path) -> dict:
    """
    Read eeg.json and extract channel counts.
    Returns dict with counts for EEG, ECG, EMG, EOG, MISC, Trigger.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    return {
        'EEGChannelCount': data.get('EEGChannelCount', 0),
        'ECGChannelCount': data.get('ECGChannelCount', 0),
        'EMGChannelCount': data.get('EMGChannelCount', 0),
        'EOGChannelCount': data.get('EOGChannelCount', 0),
        'MiscChannelCount': data.get('MiscChannelCount', 0),
        'TriggerChannelCount': data.get('TriggerChannelCount', 0)
    }


def main():
    print("Generating channel count CSV from aligned eeg.json files")
    print(f"Input: {INPUT_DIR}")
    print(f"Output: {OUTPUT_CSV}")

    if DRY_RUN:
        print("\n[DRY RUN MODE - No files will be written]")

    # Find all eeg.json files
    input_path = Path(INPUT_DIR)
    if not input_path.exists():
        print(f"ERROR: Input directory not found: {INPUT_DIR}")
        return

    json_files = list(input_path.glob("**/*_eeg.json"))
    print(f"\nFound {len(json_files)} *_eeg.json files to process")

    # Collect data
    rows = []
    errors = []

    for json_file in json_files:
        patient_id, session_dir = extract_patient_session_from_path(json_file)

        if not patient_id or not session_dir:
            print(f"  WARNING: Could not extract patient/session from: {json_file}")
            errors.append(str(json_file))
            continue

        try:
            counts = read_channel_counts(json_file)
            rows.append({
                'patient-id': patient_id,
                'session-dir': session_dir,
                'EEGChannelCount': counts['EEGChannelCount'],
                'ECGChannelCount': counts['ECGChannelCount'],
                'EMGChannelCount': counts['EMGChannelCount'],
                'EOGChannelCount': counts['EOGChannelCount'],
                'MiscChannelCount': counts['MiscChannelCount'],
                'TriggerChannelCount': counts['TriggerChannelCount']
            })
        except Exception as e:
            print(f"  ERROR reading {json_file}: {e}")
            errors.append(str(json_file))

    # Sort rows by patient-id, then session-dir
    rows.sort(key=lambda x: (x['patient-id'], x['session-dir']))

    # Write CSV
    if DRY_RUN:
        print(f"\n[DRY RUN] Would write {len(rows)} rows to {OUTPUT_CSV}")
        print("\nSample rows:")
        for row in rows[:5]:
            print(f"  {row}")
    else:
        fieldnames = ['patient-id', 'session-dir', 'EEGChannelCount', 'ECGChannelCount',
                      'EMGChannelCount', 'EOGChannelCount', 'MiscChannelCount', 'TriggerChannelCount']

        with open(OUTPUT_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nWrote {len(rows)} rows to {OUTPUT_CSV}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total eeg.json files processed: {len(json_files)}")
    print(f"Rows written: {len(rows)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were written.")
        print("Set DRY_RUN = False to execute.")


if __name__ == "__main__":
    main()
