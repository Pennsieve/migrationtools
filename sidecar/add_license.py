"""Script to add Creative Commons Attribution license to all datasets."""

import os
import requests
from helpers import get_all_datasets

API_KEY = os.getenv("PENNSIEVE_API_KEY")
BASE_URL = "https://api.pennsieve.io"


def update_dataset_licenses():
    """Update license to 'Creative Commons Attribution' for all datasets."""
    datasets = get_all_datasets()

    print(f"Found {len(datasets)} datasets to update")

    success_count = 0
    failure_count = 0

    for dataset in datasets:
        dataset_id = dataset.get("content", {}).get("id")
        dataset_name = dataset.get("content", {}).get("name", "Unknown")

        if not dataset_id:
            print(f"Skipping dataset '{dataset_name}' - no ID found")
            failure_count += 1
            continue

        url = f"{BASE_URL}/datasets/{dataset_id}?api_key={API_KEY}"
        payload = {
            "license": "Creative Commons Attribution"
        }
        headers = {
            "Content-Type": "application/json",
            "accept": "*/*"
        }

        try:
            response = requests.put(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"Updated license for dataset: {dataset_name} (ID: {dataset_id})")
            success_count += 1
        except requests.exceptions.RequestException as e:
            print(f"Failed to update dataset '{dataset_name}' (ID: {dataset_id}): {e}")
            failure_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} succeeded, {failure_count} failed out of {len(datasets)} total")
    print(f"{'='*60}")


if __name__ == "__main__":
    update_dataset_licenses()
