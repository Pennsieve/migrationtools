'''
Download all *_sessions.tsv files from Pennsieve datasets.

Files are expected at: PREVeNT Trial <patient_id>/primary/sub-<patient_id>/sub-<patient_id>_sessions.tsv

Downloads all files to a flat directory for easy batch processing.
'''

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

# Output path
OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "sessionsTsv_check", "sessionstsv_downloaded")

DRY_RUN = True  # True = print actions only, no downloads
TARGET_DATASETS = ["*"]  # ["*"] for all PREVeNT, or list specific dataset names


def should_process_dataset(dataset_name: str) -> bool:
    """Check if dataset should be processed based on TARGET_DATASETS."""
    if not dataset_name:
        return False
    if not dataset_name.startswith("PREVeNT"):
        return False
    if TARGET_DATASETS == ["*"]:
        return True
    return dataset_name in TARGET_DATASETS


def extract_patient_id_from_dataset(dataset_name: str) -> str:
    """
    Extract patient ID from dataset name.
    e.g., 'PREVeNT Trial 166V' -> '166V'
    """
    match = re.match(r"PREVeNT Trial (.+)", dataset_name)
    if match:
        return match.group(1).strip()
    return None


def extract_patient_id_from_filename(filename: str) -> str:
    """
    Extract patient ID from sessions.tsv filename.
    e.g., 'sub-166V_sessions.tsv' -> '166V'
    """
    match = re.match(r"sub-(.+)_sessions\.tsv", filename)
    if match:
        return match.group(1).strip()
    return None


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


def download_sessions_tsv():
    """Main function to download all *_sessions.tsv files to flat directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching datasets from Pennsieve...")
    datasets = get_all_datasets()
    print(f"Found {len(datasets)} total datasets")
    print(f"Output directory: {OUTPUT_DIR}")

    downloads_made = []
    errors = []

    for ds in datasets:
        dataset_name = ds.get("content", {}).get("name", "")
        dataset_id = ds.get("content", {}).get("id")

        if not should_process_dataset(dataset_name):
            continue

        patient_id = extract_patient_id_from_dataset(dataset_name)

        print(f"\n{'='*60}")
        print(f"Dataset: {dataset_name} (Patient: {patient_id})")

        if DRY_RUN:
            print("  [DRY RUN] Would check packages")
            continue

        # Get all packages in the dataset
        try:
            packages = get_dataset_packages(dataset_id)
            print(f"  Found {len(packages)} packages")
        except Exception as e:
            print(f"  Error fetching packages: {e}")
            errors.append({
                "dataset": dataset_name,
                "error": str(e)
            })
            continue

        # Find and download *_sessions.tsv files
        sessions_tsv_count = 0
        for pkg in packages:
            content = pkg.get("content", {})
            pkg_name = content.get("name", "")
            node_id = content.get("nodeId")

            # Only process *_sessions.tsv files
            if not pkg_name.endswith("_sessions.tsv"):
                continue

            sessions_tsv_count += 1
            file_patient_id = extract_patient_id_from_filename(pkg_name)

            print(f"  Found: {pkg_name}")

            try:
                file_content = download_file_content(node_id)

                output_file = Path(OUTPUT_DIR) / pkg_name

                with open(output_file, "wb") as f:
                    f.write(file_content)

                print(f"    Saved to: {output_file}")

                downloads_made.append({
                    "dataset": dataset_name,
                    "patient_id": patient_id,
                    "file_patient_id": file_patient_id,
                    "file": pkg_name,
                    "output_path": str(output_file)
                })

            except Exception as e:
                print(f"    Error downloading: {e}")
                errors.append({
                    "dataset": dataset_name,
                    "file": pkg_name,
                    "error": str(e)
                })

        if sessions_tsv_count == 0:
            print("  No *_sessions.tsv files found")

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
        for err in errors[:10]:  # Show first 10 errors
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    return {"downloads": downloads_made, "errors": errors}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download *_sessions.tsv files from Pennsieve")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print actions without downloading")

    args = parser.parse_args()

    if args.dry_run:
        DRY_RUN = True

    download_sessions_tsv()