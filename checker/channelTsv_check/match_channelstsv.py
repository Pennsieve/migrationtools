'''
Match channels.tsv files with EEG metadata and update low_cutoff/high_cutoff values.

Logic:
1. For each *_channels.tsv in channelstsv_merged/, extract patient-id and session_dir
2. Match with PID1 and session in eeg_metadata.csv (using second row as header)
3. Replace low_cutoff and high_cutoff with hardwarefilters_min and hardwarefilters_max
4. Output to channelstsv_matched/
'''

import os
import re
import csv
from pathlib import Path

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)

INPUT_METADATA_CSV = os.path.join(CHECKER_DIR, "input", "eeg_metadata.csv")
SOURCE_MERGED_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_merged")
OUTPUT_MATCHED_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_matched")

DRY_RUN = False  # True = print actions only, no file operations


def normalize_csv_value(value: str) -> str:
    """
    Normalize CSV values: if empty, 'n/a', or 'nan', return 'n/a'.
    Otherwise return the stripped value.
    """
    if not value:
        return "n/a"
    stripped = value.strip().lower()
    if stripped in ("", "n/a", "nan", "na", "none"):
        return "n/a"
    return value.strip()


def load_metadata():
    """
    Load EEG metadata CSV, using the second row as the header.
    Returns a dict: {(patient_id, session): {'hardwarefilters_min': ..., 'hardwarefilters_max': ...}}
    """
    metadata = {}

    if not os.path.exists(INPUT_METADATA_CSV):
        print(f"ERROR: Metadata CSV not found: {INPUT_METADATA_CSV}")
        return metadata

    with open(INPUT_METADATA_CSV, 'r', encoding='utf-8-sig') as f:
        # Use csv.reader to properly handle quoted fields with commas
        reader = csv.reader(f)
        all_rows = list(reader)

    if len(all_rows) < 3:
        print("ERROR: Metadata CSV has fewer than 3 rows")
        return metadata

    # Second row (index 1) is the header
    header = all_rows[1]

    # Find column indices
    try:
        pid1_idx = header.index('PID1')
        session_idx = header.index('session')
        hw_min_idx = header.index('hardwarefilters_min')
        hw_max_idx = header.index('hardwarefilters_max')
    except ValueError as e:
        print(f"ERROR: Required column not found in header: {e}")
        print(f"Available columns: {header}")
        return metadata

    # Parse data rows (starting from index 2)
    for row in all_rows[2:]:
        if len(row) <= max(pid1_idx, session_idx, hw_min_idx, hw_max_idx):
            continue

        pid1 = row[pid1_idx].strip()
        session = row[session_idx].strip()
        hw_min = normalize_csv_value(row[hw_min_idx])
        hw_max = normalize_csv_value(row[hw_max_idx])

        if pid1 and session:
            key = (pid1, session)
            metadata[key] = {
                'hardwarefilters_min': hw_min,
                'hardwarefilters_max': hw_max
            }

    return metadata


def extract_patient_session_from_path(filepath: Path):
    """
    Extract patient_id and session_dir from file path.
    e.g., .../sub-13UL/ses-visit03m/sub-13UL_ses-visit03m_task-prv_channels.tsv
    Returns (patient_id, session_dir) where patient_id is without 'sub-' prefix
    """
    parts = filepath.parts

    # Find sub-XXX folder
    patient_id = None
    session_dir = None

    for part in parts:
        if part.startswith('sub-'):
            patient_id = part[4:8]  # Remove 'sub-' prefix
        elif part.startswith('ses-'):
            session_dir = part

    return patient_id, session_dir


def process_channels_tsv(input_file: Path, output_file: Path, hw_min: str, hw_max: str):
    """
    Read channels.tsv, replace low_cutoff and high_cutoff values, write to output.
    """
    with open(input_file, 'r', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        rows = list(reader)

    if not rows:
        print(f"    WARNING: Empty file: {input_file}")
        return False

    # Find column indices from header
    header = rows[0]
    try:
        low_cutoff_idx = header.index('low_cutoff')
        high_cutoff_idx = header.index('high_cutoff')
    except ValueError as e:
        print(f"    WARNING: Column not found in {input_file}: {e}")
        return False

    # Update values in all data rows
    for i in range(1, len(rows)):
        if len(rows[i]) > max(low_cutoff_idx, high_cutoff_idx):
            rows[i][low_cutoff_idx] = hw_min
            rows[i][high_cutoff_idx] = hw_max

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(rows)

    return True


def main():
    print("Matching channels.tsv files with EEG metadata")
    print(f"Source: {SOURCE_MERGED_DIR}")
    print(f"Metadata: {INPUT_METADATA_CSV}")
    print(f"Output: {OUTPUT_MATCHED_DIR}")

    if DRY_RUN:
        print("\n[DRY RUN MODE - No files will be modified]")

    # Load metadata
    print(f"\n{'='*60}")
    print("Loading EEG metadata...")
    metadata = load_metadata()
    print(f"Loaded {len(metadata)} patient-session entries from metadata")

    if not metadata:
        print("ERROR: No metadata loaded. Exiting.")
        return

    # Create output directory
    if not DRY_RUN:
        os.makedirs(OUTPUT_MATCHED_DIR, exist_ok=True)

    # Find all channels.tsv files
    source_path = Path(SOURCE_MERGED_DIR)
    if not source_path.exists():
        print(f"ERROR: Source directory not found: {SOURCE_MERGED_DIR}")
        return

    tsv_files = list(source_path.glob("**/*_channels.tsv"))
    print(f"\nFound {len(tsv_files)} *_channels.tsv files to process")

    # Process each file
    print(f"\n{'='*60}")
    print("Processing files...")

    matched_count = 0
    not_matched = []
    errors = []

    for tsv_file in tsv_files:
        patient_id, session_dir = extract_patient_session_from_path(tsv_file)

        if not patient_id or not session_dir:
            print(f"\n  WARNING: Could not extract patient/session from: {tsv_file}")
            errors.append(str(tsv_file))
            continue

        # Lookup in metadata
        key = (patient_id, session_dir)
        if key not in metadata:
            not_matched.append(f"{patient_id}/{session_dir}")
            continue

        hw_min = metadata[key]['hardwarefilters_min']
        hw_max = metadata[key]['hardwarefilters_max']

        # Build output path (preserve folder structure)
        relative_path = tsv_file.relative_to(source_path)
        output_file = Path(OUTPUT_MATCHED_DIR) / relative_path

        print(f"\n  Processing: sub-{patient_id}/{session_dir}")
        print(f"    hw_min: {hw_min}, hw_max: {hw_max}")

        if DRY_RUN:
            print(f"    [DRY RUN] Would update: {output_file}")
            matched_count += 1
        else:
            if process_channels_tsv(tsv_file, output_file, hw_min, hw_max):
                print(f"    Saved to: {output_file}")
                matched_count += 1
            else:
                errors.append(str(tsv_file))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total files processed: {len(tsv_files)}")
    print(f"Files matched and updated: {matched_count}")
    print(f"Files not matched (no metadata): {len(not_matched)}")
    print(f"Errors: {len(errors)}")

    if not_matched:
        print(f"\nFiles without matching metadata ({len(not_matched)}):")
        for entry in not_matched[:20]:
            print(f"  - {entry}")
        if len(not_matched) > 20:
            print(f"  ... and {len(not_matched) - 20} more")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were modified.")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\nUpdated files saved to: {OUTPUT_MATCHED_DIR}")


if __name__ == "__main__":
    main()
