'''
Merge channels.tsv files from channelstsv_all and correct_channelsTsv folders.

Logic:
1. Copy all files from channelstsv_all to channelstsv_merged
2. Read the CSV list of patient-id, session-dir from channelCountChecker_jacChecked.csv
3. For each entry in the CSV, replace the channels.tsv file in channelstsv_merged
   with the corrected version from correct_channelsTsv (if it exists)
'''

import os
import csv
import shutil
from pathlib import Path

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)

INPUT_CSV = os.path.join(CHECKER_DIR, "input", "channelCountChecker_jacChecked.csv")
SOURCE_ALL_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_all")
SOURCE_CORRECT_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_corrected")
OUTPUT_MERGED_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_merged")

DRY_RUN = False  # True = print actions only, no file operations


def copy_all_to_merged():
    """Copy all files from channelstsv_all to channelstsv_merged."""
    print(f"{'='*60}")
    print("Step 1: Copying all files from channelstsv_all to channelstsv_merged")
    print(f"{'='*60}")

    if not os.path.exists(SOURCE_ALL_DIR):
        print(f"  ERROR: Source directory does not exist: {SOURCE_ALL_DIR}")
        return False

    # Remove existing merged directory if it exists
    if os.path.exists(OUTPUT_MERGED_DIR):
        if DRY_RUN:
            print(f"  [DRY RUN] Would remove existing directory: {OUTPUT_MERGED_DIR}")
        else:
            shutil.rmtree(OUTPUT_MERGED_DIR)
            print(f"  Removed existing directory: {OUTPUT_MERGED_DIR}")

    # Copy entire directory tree
    if DRY_RUN:
        print(f"  [DRY RUN] Would copy {SOURCE_ALL_DIR} to {OUTPUT_MERGED_DIR}")
    else:
        shutil.copytree(SOURCE_ALL_DIR, OUTPUT_MERGED_DIR)
        print(f"  Copied {SOURCE_ALL_DIR} to {OUTPUT_MERGED_DIR}")

    return True


def read_csv_entries():
    """Read patient-id and session-dir from the CSV file."""
    entries = []

    if not os.path.exists(INPUT_CSV):
        print(f"  ERROR: CSV file does not exist: {INPUT_CSV}")
        return entries

    with open(INPUT_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id = row.get('patient-id', '').strip()
            session_dir = row.get('session-dir', '').strip()
            if patient_id and session_dir:
                entries.append({
                    'patient_id': patient_id,
                    'session_dir': session_dir
                })

    return entries


def replace_with_correct_files(entries):
    """Replace channels.tsv files in merged folder with correct versions."""
    print(f"\n{'='*60}")
    print("Step 2: Replacing files with corrected versions")
    print(f"{'='*60}")

    replaced_count = 0
    not_found_in_correct = []
    not_found_in_merged = []

    for entry in entries:
        patient_id = entry['patient_id']
        session_dir = entry['session_dir']

        # Build paths
        correct_dir = Path(SOURCE_CORRECT_DIR) / patient_id / session_dir
        merged_dir = Path(OUTPUT_MERGED_DIR) / patient_id / session_dir

        print(f"\n  Processing: {patient_id}/{session_dir}")

        # Check if correct directory exists
        if not correct_dir.exists():
            print(f"    WARNING: Correct source directory not found: {correct_dir}")
            not_found_in_correct.append(f"{patient_id}/{session_dir}")
            continue

        # Find channels.tsv files in correct directory
        correct_tsv_files = list(correct_dir.glob("*_channels.tsv"))

        if not correct_tsv_files:
            print(f"    WARNING: No *_channels.tsv files found in: {correct_dir}")
            not_found_in_correct.append(f"{patient_id}/{session_dir}")
            continue

        for correct_file in correct_tsv_files:
            merged_file = merged_dir / correct_file.name

            if DRY_RUN:
                if merged_file.exists():
                    print(f"    [DRY RUN] Would replace: {merged_file.name}")
                else:
                    print(f"    [DRY RUN] Would copy (new): {merged_file.name}")
            else:
                # Ensure merged directory exists
                merged_dir.mkdir(parents=True, exist_ok=True)

                # Copy (overwrite) the file
                shutil.copy2(correct_file, merged_file)

                if merged_file.exists():
                    print(f"    Replaced: {merged_file.name}")
                else:
                    print(f"    Copied (new): {merged_file.name}")

            replaced_count += 1

    return replaced_count, not_found_in_correct, not_found_in_merged


def main():
    print("Merging channels.tsv files")
    print(f"Source (all): {SOURCE_ALL_DIR}")
    print(f"Source (correct): {SOURCE_CORRECT_DIR}")
    print(f"Output (merged): {OUTPUT_MERGED_DIR}")
    print(f"CSV input: {INPUT_CSV}")

    if DRY_RUN:
        print("\n[DRY RUN MODE - No files will be modified]")

    # Step 1: Copy all files to merged directory
    if not copy_all_to_merged():
        print("\nERROR: Failed to copy files. Exiting.")
        return

    # Read CSV entries
    entries = read_csv_entries()
    print(f"\nFound {len(entries)} entries in CSV to process")

    # Step 2: Replace with correct files
    replaced_count, not_found_correct, not_found_merged = replace_with_correct_files(entries)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total entries in CSV: {len(entries)}")
    print(f"Files replaced/copied: {replaced_count}")

    if not_found_correct:
        print(f"\nEntries with missing correct files ({len(not_found_correct)}):")
        for entry in not_found_correct[:10]:
            print(f"  - {entry}")
        if len(not_found_correct) > 10:
            print(f"  ... and {len(not_found_correct) - 10} more")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were modified.")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\nMerged files saved to: {OUTPUT_MERGED_DIR}")


if __name__ == "__main__":
    main()
