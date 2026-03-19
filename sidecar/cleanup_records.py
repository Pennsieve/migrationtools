#!/usr/bin/env python3
"""
Quick script to delete all records from a model.
Uses PENNSIEVE_API_KEY env variable for Bearer auth.
"""

import os
import requests
from urllib.parse import quote

API_KEY = os.getenv("PENNSIEVE_API_KEY")
BASE_URL = "https://api2.pennsieve.io"

MODEL_ID = "d533d944-71b6-4b2d-a048-b45855eba3f0"
DATASET_ID = "N:dataset:12954f4a-8291-4179-a89e-ce8bf01a395f"
ENCODED_DATASET_ID = quote(DATASET_ID, safe="")

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def get_records(cursor=None):
    """Fetch a page of records."""
    url = f"{BASE_URL}/metadata/models/{MODEL_ID}/records/search?dataset_id={ENCODED_DATASET_ID}&page_size=10"
    if cursor:
        url += f"&cursor={cursor}"

    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def delete_record(record_id):
    """Delete a single record."""
    url = f"{BASE_URL}/metadata/models/{MODEL_ID}/records/{record_id}?dataset_id={ENCODED_DATASET_ID}&force=true"
    response = requests.delete(url, headers=HEADERS)
    response.raise_for_status()
    print(f"  Deleted: {record_id}")


def main():
    if not API_KEY:
        print("ERROR: PENNSIEVE_API_KEY not set")
        return

    print(f"Fetching records from model {MODEL_ID}...")

    total_deleted = 0
    cursor = None

    while True:
        data = get_records(cursor)
        records = data.get("records", [])

        if not records:
            print("No more records.")
            break

        print(f"Found {len(records)} records, deleting...")

        for record in records:
            record_id = record.get("id")
            if record_id:
                delete_record(record_id)
                total_deleted += 1

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"\nDone! Deleted {total_deleted} records.")


if __name__ == "__main__":
    main()
