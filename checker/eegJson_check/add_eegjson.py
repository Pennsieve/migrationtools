'''
Add HeadCircumference to EEG JSON files based on metadata from a CSV file.
Reads JSON files from checker/output/eegJson_check/eegjson_aligned/
Outputs updated files to checker/output/eegJson_check/eegjson_added/
'''

import csv
import json
import os
import re
from pathlib import Path

# Paths relative to checker directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)

INPUT_DIR = os.path.join(CHECKER_DIR, "input")
OUTPUT_BASE_DIR = os.path.join(CHECKER_DIR, "output", "eegJson_check")

# Input: aligned JSON files
ALIGN_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_aligned")
# Output: JSON files with HeadCircumference added
OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_added")

METADATA_CSV_PATH = os.path.join(INPUT_DIR, "eeg_metadata.csv")

DRY_RUN = False  # True = print actions only, no file writes

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ANSI color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"


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


def load_session_metadata(csv_path: str) -> dict:
    """
    Load CSV and create mapping: (subject_id, session) -> HeadCircumference value.

    Note: The CSV has two header rows - row 1 is categories, row 2 is actual column names.
    We skip row 1 and use row 2 as headers.

    Key is composite: "subject_id|session" (e.g., "13UL|ses-visit03m")
    """
    session_metadata = {}
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        # Skip the first row (category headers)
        next(f)
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row.get("PID1", "").strip()
            session = row.get("session", "").strip()
            if not session or not subject_id:
                continue
            # Composite key: subject_id|session
            key = f"{subject_id}|{session}"
            session_metadata[key] = {
                "HeadCircumference": normalize_csv_value(row.get("Headcircumference", "")),
            }
    return session_metadata


def extract_subject_from_filename(filename: str) -> str:
    """
    Extract subject ID from EEG JSON filename.
    e.g., 'sub-13UL_ses-visit07.5m_task-prv_eeg.json' -> '13UL'
    """
    match = re.search(r"sub-([^_]+)", filename)
    if match:
        return match.group(1)
    return None


def extract_session_from_filename(filename: str) -> str:
    """
    Extract session from EEG JSON filename.
    e.g., 'sub-13UL_ses-visit07.5m_task-prv_eeg.json' -> 'ses-visit07.5m'
    """
    match = re.search(r"(ses-visit[\d.]+m)", filename)
    if match:
        return match.group(1)
    return None


def find_all_eeg_json_files(align_dir: str) -> list:
    """
    Find all *_eeg.json files in the aligned directory.
    Returns list of dicts: {subject_folder, session_folder, filename, full_path}
    """
    json_files = []
    align_path = Path(align_dir)

    if not align_path.exists():
        print(f"Error: Aligned directory not found: {align_dir}")
        return json_files

    # Walk through sub-*/ses-*/ structure
    for subject_dir in sorted(align_path.iterdir()):
        if not subject_dir.is_dir() or not subject_dir.name.startswith("sub-"):
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            for json_file in session_dir.glob("*_eeg.json"):
                json_files.append({
                    "subject_folder": subject_dir.name,
                    "session_folder": session_dir.name,
                    "filename": json_file.name,
                    "full_path": str(json_file)
                })

    return json_files


def add_head_circumference():
    """Main function to add HeadCircumference to JSON files based on CSV metadata."""

    # 1. Load session -> metadata mapping from CSV
    session_metadata = load_session_metadata(METADATA_CSV_PATH)
    print(f"Loaded {len(session_metadata)} session metadata entries from CSV")

    # 2. Find all aligned JSON files
    print(f"\nScanning for JSON files in: {ALIGN_DIR}")
    json_files = find_all_eeg_json_files(ALIGN_DIR)
    print(f"Found {len(json_files)} *_eeg.json files")

    if not json_files:
        print("No JSON files found. Run previous steps first.")
        return {"updates": [], "errors": [], "skipped": []}

    updates_made = []
    errors = []
    skipped = []

    for file_info in json_files:
        filename = file_info["filename"]
        full_path = file_info["full_path"]
        subject_folder = file_info["subject_folder"]
        session_folder = file_info["session_folder"]

        # Extract subject and session from filename
        subject_id = extract_subject_from_filename(filename)
        session = extract_session_from_filename(filename)

        if not subject_id:
            print(f"  Warning: Could not extract subject from: {filename}")
            skipped.append({"file": filename, "reason": "Could not extract subject"})
            continue

        if not session:
            print(f"  Warning: Could not extract session from: {filename}")
            skipped.append({"file": filename, "reason": "Could not extract session"})
            continue

        # Look up metadata from CSV using composite key (subject|session)
        lookup_key = f"{subject_id}|{session}"
        csv_meta = session_metadata.get(lookup_key)
        if not csv_meta:
            print(f"  Warning: No metadata found for '{lookup_key}' ({filename})")
            skipped.append({"file": filename, "reason": f"No metadata for {lookup_key}"})
            continue

        head_circumference = csv_meta.get("HeadCircumference", "n/a")

        print(f"\n  File: {filename}")
        print(f"    Subject: {subject_id}, Session: {session}")
        print(f"    HeadCircumference: {head_circumference}")

        if DRY_RUN:
            print(f"    [DRY RUN] Would add HeadCircumference = '{head_circumference}'")
        else:
            try:
                # Read JSON from local file
                with open(full_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                old_value = json_data.get("HeadCircumference", None)

                # Add HeadCircumference to JSON
                json_data["HeadCircumference"] = head_circumference

                # Save to output directory (preserving sub-*/ses-*/ structure)
                output_path = Path(OUTPUT_DIR) / subject_folder / session_folder
                output_path.mkdir(parents=True, exist_ok=True)

                output_file = output_path / filename
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=2)

                if old_value is None:
                    print(f"{GREEN}    Added: HeadCircumference = '{head_circumference}'{RESET}")
                else:
                    print(f"{GREEN}    Updated: '{old_value}' -> '{head_circumference}'{RESET}")
                print(f"    Saved to: {output_file}")

                updates_made.append({
                    "subject": subject_id,
                    "session": session,
                    "file": filename,
                    "old_value": old_value,
                    "new_value": head_circumference,
                    "output_path": str(output_file)
                })

            except Exception as e:
                print(f"{RED}    Error: {e}{RESET}")
                errors.append({
                    "file": filename,
                    "error": str(e)
                })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Updates {'would be ' if DRY_RUN else ''}made: {len(updates_made)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Errors: {len(errors)}")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were modified.")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\nUpdated JSON files saved to: {OUTPUT_DIR}/")

    return {"updates": updates_made, "errors": errors, "skipped": skipped}


if __name__ == "__main__":
    add_head_circumference()
