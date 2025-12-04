#!/usr/bin/env python3
"""
Quick script to fetch a model's schema from Pennsieve.
Uses PENNSIEVE_API_KEY env variable for Bearer auth.

Usage:
  python get_model_schema.py MODEL_ID DATASET_ID

Example:
  python get_model_schema.py 509afee2-7b74-4cd2-84d6-41f53207dde0 "N:dataset:2651f276-bf8b-4550-aa82-a69888ed803f"
"""

import os
import sys
import json
import requests
from urllib.parse import quote

API_KEY = os.getenv("PENNSIEVE_API_KEY")
BASE_URL = "https://api2.pennsieve.io"

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def main():
    if not API_KEY:
        print("ERROR: PENNSIEVE_API_KEY not set")
        return

    if len(sys.argv) < 3:
        print("Usage: python get_model_schema.py MODEL_ID DATASET_ID")
        print('Example: python get_model_schema.py 509afee2-... "N:dataset:2651f276-..."')
        return

    model_id = sys.argv[1]
    dataset_id = sys.argv[2]
    encoded_dataset_id = quote(dataset_id, safe="")

    url = f"{BASE_URL}/metadata/models/{model_id}?dataset_id={encoded_dataset_id}"

    print(f"Fetching model schema...")
    print(f"URL: {url}\n")

    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
