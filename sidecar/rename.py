"""
Rename Pennsieve datasets and their 'collection' packages
from EPSXXX format to PennEPIXXX format.
Supports dry-run and selective dataset targeting.
"""

import requests
from helpers import get_all_datasets, get_dataset_packages, generate_new_name, API_KEY


PENNSIEVE_API_BASE = "https://api.pennsieve.io"
HEADERS = {"accept": "*/*", "content-type": "application/json"}

DRY_RUN = True  # True = print actions only, no PUT requests
TARGET_DATASETS = []  # ["*"] for all, [] for none


def rename_dataset(dataset_id: str, new_name: str) -> bool:
    """Rename a dataset by ID on Pennsieve."""
    if DRY_RUN:
        print(f"[DRY-RUN] Would rename dataset ID {dataset_id} → '{new_name}'")
        return True

    if not API_KEY:
        print("❌ PENNSIEVE_API_KEY not set.")
        return False

    url = f"{PENNSIEVE_API_BASE}/datasets/{dataset_id}?api_key={API_KEY}"
    payload = {"name": new_name}

    try:
        response = requests.put(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"✅ Dataset renamed → '{new_name}' (ID: {dataset_id})")
        return True
    except requests.RequestException as e:
        print(f"❌ Failed to rename dataset {dataset_id}: {e}")
        if response := getattr(e, "response", None):
            print(f"   → {response.text}")
        return False


def rename_package(package_id: str, new_name: str) -> bool:
    """Rename a package by ID on Pennsieve."""
    if DRY_RUN:
        print(f"[DRY-RUN] Would rename package ID {package_id} → '{new_name}'")
        return True

    if not API_KEY:
        print("❌ PENNSIEVE_API_KEY not set.")
        return False

    url = f"{PENNSIEVE_API_BASE}/packages/{package_id}?updateStorage=false&api_key={API_KEY}"
    payload = {"name": new_name}

    try:
        response = requests.put(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"📦 Package renamed → '{new_name}' (ID: {package_id})")
        return True
    except requests.RequestException as e:
        print(f"❌ Failed to rename package {package_id}: {e}")
        if response := getattr(e, "response", None):
            print(f"   → {response.text}")
        return False


def should_process(dataset_name: str) -> bool:
    """Decide if this dataset should be processed based on TARGET_DATASETS."""
    if not TARGET_DATASETS:
        return False
    if TARGET_DATASETS == ["*"]:
        return True
    return dataset_name in TARGET_DATASETS


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

        new_name = generate_new_name(dataset_name)
        if new_name == dataset_name:
            print(f"↪ Skipping {dataset_name} (no rename needed)")
            continue

        # Rename dataset
        if rename_dataset(dataset_id, new_name):
            # Rename corresponding package
            packages = get_dataset_packages(dataset_id)
            for pkg in packages:
                pkg_content = pkg.get("content", "")
                pkg_name = pkg_content.get("name", "").strip()
                pkg_type = pkg_content.get("packageType", "").lower()
                package_id = pkg_content.get("nodeId", "")

                expected_pkg_name = f"sub-{dataset_name}".lower()
                if pkg_name.lower() == expected_pkg_name and pkg_type == "collection":
                    rename_package(package_id, f"sub-{new_name}")

    print("\n✅ Completed dataset processing.")
    if DRY_RUN:
        print("💡 (Dry-run mode: no actual changes were made.)")


if __name__ == "__main__":
    process_datasets()
