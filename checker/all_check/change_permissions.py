"""
Rename Pennsieve datasets and their 'collection' packages
from EPSXXX format to PennEPIXXX format.
Supports dry-run and selective dataset targeting.
"""

import os
import sys
import requests

# Add parent directories to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(CHECKER_DIR)
sys.path.insert(0, ROOT_DIR)

from helpers import get_all_datasets, get_dataset_packages, generate_new_name, API_KEY


PENNSIEVE_API_BASE = "https://api.pennsieve.io"
HEADERS = {"accept": "*/*", "content-type": "application/json"}

DRY_RUN = False  # True = print actions only, no PUT requests
TARGET_DATASETS = ["*"]  # ["*"] for all, [] for none



def should_process(dataset_name: str) -> bool:
    """
    Decide if this dataset should be processed.

    SAFETY: Only datasets starting with 'EPS' can be processed,
    even if explicitly listed in TARGET_DATASETS.
    """
    if not dataset_name:
        print(f"⚠️ Dataset name is empty, skipping.")
        return False

    # Hard safety requirement: ONLY PREVENT TRIAL datasets
    if not dataset_name.upper().startswith("PREVENT"):
        print(f"⚠️ Dataset '{dataset_name}' does not start with 'PREVeNT', skipping.")
        return False

    if not TARGET_DATASETS:
        print("⚠️ TARGET_DATASETS is empty, skipping all datasets.")
        return False

    if TARGET_DATASETS == ["*"]:
        print("ℹ️ TARGET_DATASETS is '*', processing all eligible datasets.")
        return True

    # Case-insensitive matching for flexibility
    return dataset_name.upper() in [t.upper() for t in TARGET_DATASETS]


def process_datasets():
    """Iterate through datasets, apply renaming rules, obey dry-run and target list."""
    datasets = get_all_datasets()

    if not TARGET_DATASETS:
        print("⚠️ TARGET_DATASETS is empty — doing nothing.")
        return

    for ds in datasets:
        content = ds.get("content", {})
        dataset_id = content.get("id")
        dataset_name = content.get("name", "").strip()

        if not should_process(dataset_name):
            continue

        print(f"\n🎯 Processing dataset: {dataset_name} (ID: {dataset_id})")
        add_team_collaborators_to_datasets(dry_run=DRY_RUN)


    print("\n✅ Completed dataset processing.")
    if DRY_RUN:
        print("💡 (Dry-run mode: no actual changes were made.)")


def add_team_collaborators_to_datasets(dry_run: bool = True):
    """
    Add team collaborators to PennEPI datasets.

    Only processes datasets with names starting with "PennEPI".

    Args:
        dry_run: If True, only prints what would be done without making changes.
                 If False, actually makes the API calls.

    Returns:
        Dictionary with results of the operation including successes and failures.
    """
    TEAM_ID = "N:team:c164398f-aaa3-4531-a284-6e30352f4e97"
    TEAM_ROLE = "editor"

    print(f"{'[DRY RUN] ' if dry_run else ''}Fetching all datasets...")
    datasets = get_all_datasets()

    # Filter to only PREVeNT Trial datasets
    prevent_dataset = [ds for ds in datasets if ds.get("content", {}).get("name", "").startswith("PREVeNT Trial")]

    print(f"Found {len(prevent_dataset)} PREVeNT Trial datasets out of {len(datasets)} total datasets\n")

    results = {
        "processed": [],
        "skipped": [],
        "errors": []
    }

    for dataset in prevent_dataset:
        dataset_name = dataset.get("content", {}).get("name", "Unknown")
        dataset_node_id = dataset.get("content", {}).get("id") or dataset.get("content", {}).get("intId")

        if not dataset_node_id:
            print(f"⚠️  Skipping {dataset_name}: No node ID found")
            results["skipped"].append({
                "name": dataset_name,
                "reason": "No node ID found"
            })
            continue

        if dry_run:
            print(f"[DRY RUN] Would add team {TEAM_ID} as {TEAM_ROLE} to dataset: {dataset_name} (ID: {dataset_node_id})")
            results["processed"].append({
                "name": dataset_name,
                "node_id": dataset_node_id,
                "status": "dry_run"
            })
        else:
            try:
                url = f"{PENNSIEVE_API_BASE}/datasets/{dataset_node_id}/collaborators/teams"
                headers = {
                    "accept": "*/*",
                    "content-type": "application/json"
                }
                payload = {
                    "id": TEAM_ID,
                    "role": TEAM_ROLE
                }

                response = requests.put(
                    f"{url}?api_key={API_KEY}",
                    json=payload,
                    headers=headers
                )
                if response.status_code in [200, 201, 204]:
                    print(f"✅ Successfully added team to: {dataset_name}")
                    results["processed"].append({
                        "name": dataset_name,
                        "node_id": dataset_node_id,
                        "status": "success"
                    })
                else:
                    print(f"❌ Failed to add team to {dataset_name}: {response.status_code} - {response.text}")
                    results["errors"].append({
                        "name": dataset_name,
                        "node_id": dataset_node_id,
                        "status_code": response.status_code,
                        "error": response.text
                    })

            except Exception as e:
                print(f"❌ Error processing {dataset_name}: {str(e)}")
                results["errors"].append({
                    "name": dataset_name,
                    "node_id": dataset_node_id,
                    "error": str(e)
                })

    # Print summary
    print(f"\n{'='*60}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  Processed: {len(results['processed'])}")
    print(f"  Skipped: {len(results['skipped'])}")
    print(f"  Errors: {len(results['errors'])}")
    print(f"{'='*60}")

    return results

if __name__ == "__main__":
     add_team_collaborators_to_datasets(dry_run=False)
