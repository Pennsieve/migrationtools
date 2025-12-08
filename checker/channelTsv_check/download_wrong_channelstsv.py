'''
Download _channels.tsv files from Pennsieve for sessions listed in the CSV.
Matches patient IDs from CSV (sub-<patient_id>) to datasets (PREVeNT Trial <patient_id>).
'''

import csv
import os
import re
import sys
import requests
from pathlib import Path

# Add parent directories to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(CHECKER_DIR)
sys.path.insert(0, ROOT_DIR)

from helpers import get_all_datasets, get_dataset_packages, API_KEY

# Input/Output paths relative to checker directory
INPUT_DIR = os.path.join(CHECKER_DIR, "input")
OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check")

CSV_PATH = os.path.join(INPUT_DIR, "channelCountChecker_jacChecked.csv")

DRY_RUN = False  # True = print actions only, no downloads

os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_patient_id(patient_id_str: str) -> str:
    """
    Parse patient ID from format 'sub-<patient_id>'.
    e.g., 'sub-166V' -> '166V'
    """
    match = re.match(r"sub-(.+)", patient_id_str)
    if match:
        return match.group(1)
    return patient_id_str


def load_csv_data(csv_path: str) -> list:
    """
    Load CSV and return list of dicts with patient_id and session_dir.
    """
    rows = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id_raw = row.get("patient-id", "").strip()
            session_dir = row.get("session-dir", "").strip()

            if patient_id_raw and session_dir:
                patient_id = parse_patient_id(patient_id_raw)
                rows.append({
                    "patient_id": patient_id,
                    "session_dir": session_dir,
                    "full_patient_id": patient_id_raw
                })
    return rows


def download_file_content(node_id: str) -> bytes:
    """Download file content from Pennsieve and return as bytes."""
    url = "https://api.pennsieve.io/packages/download-manifest"
    payload = {"nodeIds": [node_id]}
    headers = {"accept": "*/*", "content-type": "application/json"}

    resp = requests.post(f"{url}?api_key={API_KEY}", json=payload, headers=headers)
    resp.raise_for_status()

    data = resp.json().get("data", [])
    if not data:
        raise ValueError(f"No download URL returned for node_id: {node_id}")

    download_url = data[0]["url"]
    return requests.get(download_url).content


def get_package_path(pkg: dict, all_packages: list) -> str:
    """
    Build the full path for a package by traversing parent IDs.
    Returns path like 'sub-166V/ses-visit07.5m/eeg/filename.tsv'
    """
    content = pkg.get("content", {})
    parent_id = content.get("parentId")
    pkg_name = content.get("name", "")

    path_parts = [pkg_name]

    # Build parent lookup
    id_to_pkg = {p.get("content", {}).get("id"): p for p in all_packages}

    # Traverse up the tree
    visited = set()
    current_parent = parent_id
    while current_parent and current_parent not in visited:
        visited.add(current_parent)
        parent_pkg = id_to_pkg.get(current_parent)
        if parent_pkg:
            parent_content = parent_pkg.get("content", {})
            parent_name = parent_content.get("name", "")
            if parent_name:
                path_parts.insert(0, parent_name)
            current_parent = parent_content.get("parentId")
        else:
            break

    return "/".join(path_parts)


def download_channels_tsv():
    """Main function to download _channels.tsv files."""

    # 1. Load CSV data
    csv_rows = load_csv_data(CSV_PATH)
    print(f"Loaded {len(csv_rows)} entries from CSV")

    # Build lookup: patient_id -> list of session_dirs
    patient_sessions = {}
    for row in csv_rows:
        pid = row["patient_id"]
        if pid not in patient_sessions:
            patient_sessions[pid] = []
        patient_sessions[pid].append(row["session_dir"])

    print(f"Found {len(patient_sessions)} unique patients")

    # 2. Get all datasets from Pennsieve
    print("\nFetching datasets from Pennsieve...")
    datasets = get_all_datasets()
    print(f"Found {len(datasets)} total datasets")

    # Build dataset lookup: patient_id -> dataset
    dataset_lookup = {}
    for ds in datasets:
        dataset_name = ds.get("content", {}).get("name", "")
        # Match format: "PREVeNT Trial <patient_id>"
        match = re.match(r"PREVeNT Trial (.+)", dataset_name)
        if match:
            patient_id = match.group(1).strip()
            dataset_lookup[patient_id] = ds

    print(f"Found {len(dataset_lookup)} PREVeNT Trial datasets")

    downloads_made = []
    errors = []

    # 3. Process each patient from CSV
    for patient_id, session_dirs in patient_sessions.items():
        dataset = dataset_lookup.get(patient_id)

        if not dataset:
            print(f"\nWarning: No dataset found for patient {patient_id}")
            errors.append({
                "patient_id": patient_id,
                "error": "Dataset not found"
            })
            continue

        dataset_name = dataset.get("content", {}).get("name", "")
        dataset_id = dataset.get("content", {}).get("id")

        print(f"\n{'='*60}")
        print(f"Patient: {patient_id}")
        print(f"Dataset: {dataset_name}")
        print(f"Sessions to check: {session_dirs}")

        # 4. Get all packages in the dataset
        try:
            packages = get_dataset_packages(dataset_id)
            print(f"Found {len(packages)} packages")
        except Exception as e:
            print(f"  Error fetching packages: {e}")
            errors.append({
                "patient_id": patient_id,
                "dataset": dataset_name,
                "error": str(e)
            })
            continue

        # Build package path lookup
        pkg_paths = {}
        for pkg in packages:
            path = get_package_path(pkg, packages)
            pkg_paths[pkg.get("content", {}).get("id")] = path

        # 5. Find _channels.tsv files in matching session folders
        for pkg in packages:
            content = pkg.get("content", {})
            pkg_name = content.get("name", "")
            node_id = content.get("nodeId")
            pkg_id = content.get("id")

            # Only process *_channels.tsv files
            if not pkg_name.endswith("_channels.tsv"):
                continue

            # Get full path and check if it's in a target session
            pkg_path = pkg_paths.get(pkg_id, pkg_name)

            # Check if this file is in one of the target sessions
            session_match = None
            for session_dir in session_dirs:
                if f"/{session_dir}/" in f"/{pkg_path}/" or pkg_path.startswith(f"{session_dir}/"):
                    session_match = session_dir
                    break

            if not session_match:
                continue

            print(f"\n  Found: {pkg_path}")
            print(f"    Session: {session_match}")
            print(f"    NodeID: {node_id}")

            # 6. Download the file
            if DRY_RUN:
                print(f"    [DRY RUN] Would download {pkg_name}")
            else:
                try:
                    file_content = download_file_content(node_id)

                    # Create output subfolder: output/channelTsv_check/<patient_id>/<session>/
                    output_subdir = Path(OUTPUT_DIR) / f"sub-{patient_id}" / session_match
                    output_subdir.mkdir(parents=True, exist_ok=True)

                    output_file = output_subdir / pkg_name
                    with open(output_file, "wb") as f:
                        f.write(file_content)

                    print(f"    Saved to: {output_file}")

                    downloads_made.append({
                        "patient_id": patient_id,
                        "dataset": dataset_name,
                        "session": session_match,
                        "file": pkg_name,
                        "output_path": str(output_file)
                    })

                except Exception as e:
                    print(f"    Error downloading: {e}")
                    errors.append({
                        "patient_id": patient_id,
                        "dataset": dataset_name,
                        "file": pkg_name,
                        "error": str(e)
                    })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Downloads {'would be ' if DRY_RUN else ''}made: {len(downloads_made)}")
    print(f"Errors: {len(errors)}")

    if DRY_RUN:
        print("\n[DRY RUN MODE] No files were downloaded.")
        print("Set DRY_RUN = False to execute.")
    else:
        print(f"\nDownloaded files saved to: {OUTPUT_DIR}/")

    if errors:
        print("\nErrors encountered:")
        for err in errors:
            print(f"  - {err}")

    return {"downloads": downloads_made, "errors": errors}


if __name__ == "__main__":
    download_channels_tsv()
