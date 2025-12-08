'''
Update EEG JSON files based on metadata from a CSV file.
Reads JSON files from checker/output/eegJson_check/download_eegJson/
Outputs matched files to checker/output/eegJson_check/eegJson_matched/
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

# Input: downloaded JSON files
DOWNLOAD_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_downloaded")
# Output: matched/fixed JSON files
OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "eegjson_matched")

METADATA_CSV_PATH = os.path.join(INPUT_DIR, "eeg_metadata.csv")

DRY_RUN = False  # True = print actions only, no file writes

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ANSI color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"


def load_session_metadata(csv_path: str) -> dict:
    """
    Load CSV and create mapping: (subject_id, session) -> metadata dict.
    Contains scheme and validation fields.

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
                "scheme": row.get("scheme", "").strip(),
                "site_F11": row.get("site_F11", "").strip(),
                "F11SYSTEM": row.get("F11SYSTEM", "").strip(),
                "ManufacturersModelName": row.get("ManufacturersModelName", "").strip(),
                "hardwarefilters_min": row.get("hardwarefilters_min", "").strip(),
                "hardwarefilters_max": row.get("hardwarefilters_max", "").strip(),
            }
    return session_metadata


def validate_json_against_csv(json_data: dict, csv_metadata: dict) -> list:
    """
    Validate JSON fields against CSV metadata.
    Returns list of mismatches found.

    Mapping:
      JSON InstitutionName <-> CSV site_F11
      JSON Manufacturer <-> CSV F11SYSTEM
      JSON ManufacturerModelName <-> CSV ManufacturersModelName
      JSON HardwareFilters.min (Hz) <-> CSV hardwarefilters_min
      JSON HardwareFilters.max (Hz) <-> CSV hardwarefilters_max
    """
    mismatches = []

    # InstitutionName vs site_F11
    json_institution = str(json_data.get("InstitutionName", "")).strip()
    csv_institution = csv_metadata.get("site_F11", "")
    if csv_institution and json_institution != csv_institution:
        mismatches.append({
            "field": "InstitutionName",
            "json_value": json_institution,
            "csv_value": csv_institution,
            "csv_column": "site_F11"
        })

    # Manufacturer vs F11SYSTEM
    json_manufacturer = str(json_data.get("Manufacturer", "")).strip()
    csv_manufacturer = csv_metadata.get("F11SYSTEM", "")
    if csv_manufacturer and json_manufacturer != csv_manufacturer:
        mismatches.append({
            "field": "Manufacturer",
            "json_value": json_manufacturer,
            "csv_value": csv_manufacturer,
            "csv_column": "F11SYSTEM"
        })

    # ManufacturerModelName vs ManufacturersModelName
    json_model = str(json_data.get("ManufacturerModelName", "")).strip()
    csv_model = csv_metadata.get("ManufacturersModelName", "")
    if csv_model and json_model != csv_model:
        mismatches.append({
            "field": "ManufacturerModelName",
            "json_value": json_model,
            "csv_value": csv_model,
            "csv_column": "ManufacturersModelName"
        })

    # HardwareFilters min/max
    hw_filters = json_data.get("HardwareFilters", {})
    hw_bandwidth = hw_filters.get("Hardware bandwidth filter", {})

    json_min = str(hw_bandwidth.get("min (Hz)", "")).strip()
    csv_min = csv_metadata.get("hardwarefilters_min", "")
    if csv_min and json_min != csv_min:
        mismatches.append({
            "field": "HardwareFilters.min (Hz)",
            "json_value": json_min,
            "csv_value": csv_min,
            "csv_column": "hardwarefilters_min"
        })

    json_max = str(hw_bandwidth.get("max (Hz)", "")).strip()
    csv_max = csv_metadata.get("hardwarefilters_max", "")
    if csv_max and json_max != csv_max:
        mismatches.append({
            "field": "HardwareFilters.max (Hz)",
            "json_value": json_max,
            "csv_value": csv_max,
            "csv_column": "hardwarefilters_max"
        })

    return mismatches


def apply_csv_fixes_to_json(json_data: dict, csv_metadata: dict) -> list:
    """
    Apply fixes from CSV metadata to JSON data.
    Returns list of changes made.

    Mapping:
      JSON InstitutionName <- CSV site_F11
      JSON Manufacturer <- CSV F11SYSTEM
      JSON ManufacturerModelName <- CSV ManufacturersModelName
      JSON HardwareFilters.min (Hz) <- CSV hardwarefilters_min
      JSON HardwareFilters.max (Hz) <- CSV hardwarefilters_max
    """
    changes = []

    # InstitutionName <- site_F11
    csv_institution = csv_metadata.get("site_F11", "")
    if csv_institution:
        old_val = str(json_data.get("InstitutionName", "")).strip()
        if old_val != csv_institution:
            json_data["InstitutionName"] = csv_institution
            changes.append({
                "field": "InstitutionName",
                "old_value": old_val,
                "new_value": csv_institution
            })

    # Manufacturer <- F11SYSTEM
    csv_manufacturer = csv_metadata.get("F11SYSTEM", "")
    if csv_manufacturer:
        old_val = str(json_data.get("Manufacturer", "")).strip()
        if old_val != csv_manufacturer:
            json_data["Manufacturer"] = csv_manufacturer
            changes.append({
                "field": "Manufacturer",
                "old_value": old_val,
                "new_value": csv_manufacturer
            })

    # ManufacturerModelName <- ManufacturersModelName
    csv_model = csv_metadata.get("ManufacturersModelName", "")
    if csv_model:
        old_val = str(json_data.get("ManufacturerModelName", "")).strip()
        if old_val != csv_model:
            json_data["ManufacturerModelName"] = csv_model
            changes.append({
                "field": "ManufacturerModelName",
                "old_value": old_val,
                "new_value": csv_model
            })

    # HardwareFilters min/max
    # Ensure HardwareFilters structure exists
    if "HardwareFilters" not in json_data:
        json_data["HardwareFilters"] = {}
    if "Hardware bandwidth filter" not in json_data["HardwareFilters"]:
        json_data["HardwareFilters"]["Hardware bandwidth filter"] = {}

    hw_bandwidth = json_data["HardwareFilters"]["Hardware bandwidth filter"]

    csv_min = csv_metadata.get("hardwarefilters_min", "")
    if csv_min:
        old_val = str(hw_bandwidth.get("min (Hz)", "")).strip()
        if old_val != csv_min:
            hw_bandwidth["min (Hz)"] = csv_min
            changes.append({
                "field": "HardwareFilters.min (Hz)",
                "old_value": old_val,
                "new_value": csv_min
            })

    csv_max = csv_metadata.get("hardwarefilters_max", "")
    if csv_max:
        old_val = str(hw_bandwidth.get("max (Hz)", "")).strip()
        if old_val != csv_max:
            hw_bandwidth["max (Hz)"] = csv_max
            changes.append({
                "field": "HardwareFilters.max (Hz)",
                "old_value": old_val,
                "new_value": csv_max
            })

    return changes


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


def find_all_eeg_json_files(download_dir: str) -> list:
    """
    Find all *_eeg.json files in the download directory.
    Returns list of tuples: (subject_folder, session_folder, filename, full_path)
    """
    json_files = []
    download_path = Path(download_dir)

    if not download_path.exists():
        print(f"Error: Download directory not found: {download_dir}")
        return json_files

    # Walk through sub-*/ses-*/ structure
    for subject_dir in sorted(download_path.iterdir()):
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


def update_eeg_jsons():
    """Main function to update JSON files based on CSV metadata."""

    # 1. Load session -> metadata mapping from CSV
    session_metadata = load_session_metadata(METADATA_CSV_PATH)
    print(f"Loaded {len(session_metadata)} session metadata entries from CSV")

    # 2. Find all downloaded JSON files
    print(f"\nScanning for JSON files in: {DOWNLOAD_DIR}")
    json_files = find_all_eeg_json_files(DOWNLOAD_DIR)
    print(f"Found {len(json_files)} *_eeg.json files")

    if not json_files:
        print("No JSON files found. Run download_eegjson.py first.")
        return {"updates": [], "errors": []}

    updates_made = []
    errors = []

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
            continue

        if not session:
            print(f"  Warning: Could not extract session from: {filename}")
            continue

        # Look up metadata from CSV using composite key (subject|session)
        lookup_key = f"{subject_id}|{session}"
        csv_meta = session_metadata.get(lookup_key)
        if not csv_meta:
            print(f"  Warning: No metadata found for '{lookup_key}' ({filename})")
            continue

        scheme = csv_meta.get("scheme", "")
        if not scheme:
            print(f"  Warning: No scheme found for session '{session}' ({filename})")
            continue

        print(f"\n  File: {filename}")
        print(f"    Subject: {subject_id}, Session: {session}")
        print(f"    Scheme: {scheme}")

        if DRY_RUN:
            print(f"    [DRY RUN] Would update EEGPlacementScheme = '{scheme}'")
        else:
            try:
                # Read JSON from local file
                with open(full_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                old_value = json_data.get("EEGPlacementScheme", "n/a")

                # Validate JSON fields against CSV and apply fixes
                mismatches = validate_json_against_csv(json_data, csv_meta)
                if mismatches:
                    print(f"{RED}    MISMATCHES FOUND (will be fixed):{RESET}")
                    for m in mismatches:
                        print(f"{RED}      {m['field']}: JSON='{m['json_value']}' -> CSV({m['csv_column']})='{m['csv_value']}'{RESET}")

                # Apply fixes from CSV to JSON (updates json_data in place)
                fixes_applied = apply_csv_fixes_to_json(json_data, csv_meta)
                if fixes_applied:
                    print(f"{GREEN}    FIXES APPLIED:{RESET}")
                    for fix in fixes_applied:
                        print(f"{GREEN}      {fix['field']}: '{fix['old_value']}' -> '{fix['new_value']}'{RESET}")

                # Update EEGPlacementScheme
                json_data["EEGPlacementScheme"] = scheme

                # Save to output directory (preserving sub-*/ses-*/ structure)
                output_path = Path(OUTPUT_DIR) / subject_folder / session_folder
                output_path.mkdir(parents=True, exist_ok=True)

                output_file = output_path / filename
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=2)

                print(f"    Updated: '{old_value}' -> '{scheme}'")
                print(f"    Saved to: {output_file}")

                updates_made.append({
                    "subject": subject_id,
                    "session": session,
                    "file": filename,
                    "old_value": old_value,
                    "new_value": scheme,
                    "output_path": str(output_file),
                    "mismatches": mismatches,
                    "fixes_applied": fixes_applied
                })

            except Exception as e:
                print(f"    Error: {e}")
                errors.append({
                    "file": filename,
                    "error": str(e)
                })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Updates {'would be ' if DRY_RUN else ''}made: {len(updates_made)}")

    # Count files with fixes and total fixes
    files_with_fixes = sum(1 for u in updates_made if u.get("fixes_applied"))
    total_fixes = sum(len(u.get("fixes_applied", [])) for u in updates_made)
    if total_fixes > 0:
        print(f"{GREEN}Files with CSV fixes applied: {files_with_fixes}{RESET}")
        print(f"{GREEN}Total field fixes applied: {total_fixes}{RESET}")

    print(f"Errors: {len(errors)}")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were modified.")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\nUpdated JSON files saved to: {OUTPUT_DIR}/")

    return {"updates": updates_made, "errors": errors}


if __name__ == "__main__":
    update_eeg_jsons()
