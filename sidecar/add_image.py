"""
Bulk update banners for all PennEPI datasets on Pennsieve.
"""

import os
import requests
from helpers import get_all_datasets

# --- Configuration -----------------------------------------------------------

API_KEY = os.getenv("PENNSIEVE_API_KEY", "")
IMAGE_PATH = "/Users/ddefreitas/Pictures/penn_logo.png"  # local path to banner
DRY_RUN = False  # True = preview only (no uploads)
PREFIX = "PennEPI"  # Dataset name prefix to match

PENNSIEVE_API_BASE = "https://api.pennsieve.io"
HEADERS = {"accept": "*/*"}

# --- Functions ---------------------------------------------------------------

def upload_banner(dataset_id: str, dataset_name: str) -> bool:
    """Upload banner image to a dataset."""
    url = f"{PENNSIEVE_API_BASE}/datasets/{dataset_id}/banner?api_key={API_KEY}"

    if DRY_RUN:
        print(f"[DRY-RUN] Would upload banner to: {dataset_name} ({dataset_id})")
        return True

    try:
        with open(IMAGE_PATH, "rb") as img_file:
            files = {"banner": (os.path.basename(IMAGE_PATH), img_file, "image/png")}
            response = requests.put(url, headers=HEADERS, files=files)
            response.raise_for_status()
        print(f"✅ Banner updated for {dataset_name} ({dataset_id})")
        return True
    except requests.RequestException as e:
        print(f"❌ Failed to update banner for {dataset_name}: {e}")
        if response := getattr(e, "response", None):
            print(f"   → {response.text}")
        return False
    except FileNotFoundError:
        print(f"❌ Banner file not found: {IMAGE_PATH}")
        return False


def process_datasets():
    """Find and update all datasets beginning with PennEPI."""
    if not API_KEY:
        print("❌ PENNSIEVE_API_KEY not set in environment.")
        return

    datasets = get_all_datasets()
    matches = [
        ds for ds in datasets
        if ds.get("content", {}).get("name", "").strip().lower().startswith(PREFIX.lower())
    ]

    if not matches:
        print(f"⚠️ No datasets found starting with '{PREFIX}'.")
        return

    print(f"📦 Found {len(matches)} datasets starting with '{PREFIX}'")
    for ds in matches:
        content = ds.get("content", {})
        dataset_id = content.get("id")
        dataset_name = content.get("name", "").strip()

        if not dataset_id or not dataset_name:
            continue

        upload_banner(dataset_id, dataset_name)

    if DRY_RUN:
        print("\n💡 Dry-run complete — no actual uploads performed.")
    else:
        print("\n✅ Finished banner updates.")


# --- Run ---------------------------------------------------------------------

if __name__ == "__main__":
    process_datasets()
