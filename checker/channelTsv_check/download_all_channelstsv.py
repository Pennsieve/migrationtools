'''
Download all *_channels.tsv files from Pennsieve datasets.
Organizes files by dataset/session folder structure.
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
OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "channelTsv_check", "channelstsv_all")

DRY_RUN = False  # True = print actions only, no downloads
TARGET_DATASETS = ["PREVeNT Trial 4L53"]  # ["*"] for all PREVeNT, or list specific dataset names

os.makedirs(OUTPUT_DIR, exist_ok=True)


def should_process_dataset(dataset_name: str) -> bool:
    """Check if dataset should be processed based on TARGET_DATASETS."""
    if not dataset_name:
        return False
    if not dataset_name.startswith("PREVeNT Trial 4L53"):
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


def extract_session_from_filename(filename: str) -> str:
    """
    Extract session from channels.tsv filename.
    e.g., 'sub-13UL_ses-visit07.5m_task-prv_channels.tsv' -> 'ses-visit07.5m'
    """
    match = re.search(r"(ses-visit[\d.]+m)", filename)
    if match:
        return match.group(1)
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


def download_channels_tsvs():
    """Main function to download all *_channels.tsv files."""

    print("Fetching datasets from Pennsieve...")
    datasets = get_all_datasets()
    print(f"Found {len(datasets)} total datasets")

    downloads_made = []
    errors = []

    for ds in datasets:
        dataset_name = ds.get("content", {}).get("name", "")
        dataset_id = ds.get("content", {}).get("id")

        if not should_process_dataset(dataset_name):
            continue

        patient_id = extract_patient_id_from_dataset(dataset_name)

        print(f"\n{'='*60}")
        print(f"Dataset: {dataset_name}")

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

        # Find and download *_channels.tsv files
        channels_tsv_count = 0
        for pkg in packages:
            content = pkg.get("content", {})
            pkg_name = content.get("name", "")
            node_id = content.get("nodeId")

            # Only process *_channels.tsv files
            if not pkg_name.endswith("_channels.tsv"):
                continue

            channels_tsv_count += 1
            session = extract_session_from_filename(pkg_name)

            print(f"  Found: {pkg_name}")

            try:
                file_content = download_file_content(node_id)

                # Create output subfolder: output/channelTsv_check/channelstsv_all/<patient_id>/<session>/
                if patient_id and session:
                    output_subdir = Path(OUTPUT_DIR) / f"sub-{patient_id}" / session
                elif patient_id:
                    output_subdir = Path(OUTPUT_DIR) / f"sub-{patient_id}"
                    print(f"    Warning: Session not found in filename '{pkg_name}'")
                else:
                    safe_dataset_name = dataset_name.replace(" ", "_").replace("/", "_")
                    output_subdir = Path(OUTPUT_DIR) / safe_dataset_name
                    print(f"    Warning: Patient ID not found in dataset name '{dataset_name}'")

                output_subdir.mkdir(parents=True, exist_ok=True)

                output_file = output_subdir / pkg_name
                with open(output_file, "wb") as f:
                    f.write(file_content)

                print(f"    Saved to: {output_file}")

                downloads_made.append({
                    "dataset": dataset_name,
                    "patient_id": patient_id,
                    "session": session,
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

        if channels_tsv_count == 0:
            print("  No *_channels.tsv files found")

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
    download_channels_tsvs()
