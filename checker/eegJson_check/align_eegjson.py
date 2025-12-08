'''
Align eeg.json files with channel counts from channels.tsv files.

Logic:
1. Iterate all *_eeg.json files in eegjson_matched/
2. Extract patient-id and session_dir from the path
3. Find corresponding *_channels.tsv in channelstsv_matched/
4. Count channel types (EEG, ECG, EMG, EOG, MISC, TRIG) from channels.tsv
5. Update the channel count keys in eeg.json
6. Output to eegjson_aligned/
'''

import csv
import json
import os
from pathlib import Path

# Paths relative to checker directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)

OUTPUT_BASE_DIR = os.path.join(CHECKER_DIR, "output", "eegJson_check")
CHANNELS_TSV_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_matched")

# Input: matched JSON files
INPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_matched")
# Output: aligned JSON files
OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_aligned")

DRY_RUN = False  # True = print actions only, no file writes

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ANSI color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"


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
            patient_id = part[:8]  # Keep full 'sub-XXXX' format
        elif part.startswith('ses-'):
            session_dir = part

    return patient_id, session_dir


def count_channel_types(channels_tsv_path: Path) -> dict:
    """
    Read channels.tsv and count occurrences of each channel type.
    Returns dict with counts for EEG, ECG, EMG, EOG, MISC, TRIG.
    """
    counts = {
        'EEG': 0,
        'ECG': 0,
        'EMG': 0,
        'EOG': 0,
        'MISC': 0,
        'TRIG': 0
    }

    if not channels_tsv_path.exists():
        return None

    with open(channels_tsv_path, 'r', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            channel_type = row.get('type', '').strip().upper()
            if channel_type == 'EEG':
                counts['EEG'] += 1
            elif channel_type == 'ECG':
                counts['ECG'] += 1
            elif channel_type == 'EMG':
                counts['EMG'] += 1
            elif channel_type == 'EOG':
                counts['EOG'] += 1
            elif channel_type == 'MISC':
                counts['MISC'] += 1
            elif channel_type in ('TRIG', 'TRIGGER'):
                counts['TRIG'] += 1

    return counts


def find_channels_tsv(patient_id: str, session_dir: str) -> Path:
    """
    Find the channels.tsv file for a given patient and session.
    Returns the path to the channels.tsv file, or None if not found.
    """
    channels_dir = Path(CHANNELS_TSV_DIR) / patient_id / session_dir

    if not channels_dir.exists():
        return None

    # Find *_channels.tsv file in the directory
    tsv_files = list(channels_dir.glob("*_channels.tsv"))
    if tsv_files:
        return tsv_files[0]

    return None


def update_eeg_json(json_path: Path, output_path: Path, counts: dict) -> bool:
    """
    Read eeg.json, update channel counts, and write to output.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Update channel counts
    data['EEGChannelCount'] = counts['EEG']
    data['ECGChannelCount'] = counts['ECG']
    data['EMGChannelCount'] = counts['EMG']
    data['EOGChannelCount'] = counts['EOG']
    data['MiscChannelCount'] = counts['MISC']
    data['TriggerChannelCount'] = counts['TRIG']

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    return True


def main():
    print("Aligning eeg.json files with channel counts from channels.tsv")
    print(f"Input eeg.json: {INPUT_DIR}")
    print(f"Input channels.tsv: {CHANNELS_TSV_DIR}")
    print(f"Output: {OUTPUT_DIR}")

    if DRY_RUN:
        print(f"\n{RED}[DRY RUN MODE - No files will be written]{RESET}")

    # Find all eeg.json files
    input_path = Path(INPUT_DIR)
    if not input_path.exists():
        print(f"ERROR: Input directory not found: {INPUT_DIR}")
        return

    json_files = list(input_path.glob("**/*_eeg.json"))
    print(f"\nFound {len(json_files)} *_eeg.json files to process")

    # Process each file
    print(f"\n{'='*60}")
    print("Processing files...")

    aligned_count = 0
    no_channels_tsv = []
    errors = []

    for json_file in json_files:
        patient_id, session_dir = extract_patient_session_from_path(json_file)

        if not patient_id or not session_dir:
            print(f"\n  {RED}WARNING: Could not extract patient/session from: {json_file}{RESET}")
            errors.append(str(json_file))
            continue

        # Find corresponding channels.tsv
        channels_tsv = find_channels_tsv(patient_id, session_dir)

        if not channels_tsv:
            no_channels_tsv.append(f"{patient_id}/{session_dir}")
            continue

        # Count channel types
        counts = count_channel_types(channels_tsv)

        if counts is None:
            print(f"\n  {RED}WARNING: Could not read channels.tsv: {channels_tsv}{RESET}")
            errors.append(str(json_file))
            continue

        # Build output path (preserve folder structure)
        relative_path = json_file.relative_to(input_path)
        output_file = Path(OUTPUT_DIR) / relative_path

        print(f"\n  Processing: {patient_id}/{session_dir}")
        print(f"    Channels: EEG={counts['EEG']}, ECG={counts['ECG']}, EMG={counts['EMG']}, "
              f"EOG={counts['EOG']}, MISC={counts['MISC']}, TRIG={counts['TRIG']}")

        if DRY_RUN:
            print(f"    [DRY RUN] Would update: {output_file}")
            aligned_count += 1
        else:
            try:
                if update_eeg_json(json_file, output_file, counts):
                    print(f"    {GREEN}Saved to: {output_file}{RESET}")
                    aligned_count += 1
            except Exception as e:
                print(f"    {RED}ERROR: {e}{RESET}")
                errors.append(str(json_file))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total eeg.json files: {len(json_files)}")
    print(f"Files aligned: {aligned_count}")
    print(f"Files without matching channels.tsv: {len(no_channels_tsv)}")
    print(f"Errors: {len(errors)}")

    if no_channels_tsv:
        print(f"\n{RED}Files without matching channels.tsv ({len(no_channels_tsv)}):{RESET}")
        for entry in no_channels_tsv[:20]:
            print(f"  - {entry}")
        if len(no_channels_tsv) > 20:
            print(f"  ... and {len(no_channels_tsv) - 20} more")

    if errors:
        print(f"\n{RED}Errors ({len(errors)}):{RESET}")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if DRY_RUN:
        print(f"\n{RED}[DRY RUN MODE] No files were written.{RESET}")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\n{GREEN}Aligned files saved to: {OUTPUT_DIR}{RESET}")


if __name__ == "__main__":
    main()
