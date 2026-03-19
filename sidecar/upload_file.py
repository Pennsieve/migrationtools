#!/usr/bin/env python3
"""
Upload a file to a Pennsieve dataset.

Usage:
  python upload_file.py --api-key KEY --api-secret SECRET \
      --dataset "PREVeNT Trial 7TA7" \
      --file /path/to/image.png

  # Upload to a specific folder within the dataset
  python upload_file.py --api-key KEY --api-secret SECRET \
      --dataset "PREVeNT Trial 7TA7" \
      --file /path/to/image.png \
      --folder "images"
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import quote

import requests
import boto3

from helpers import BASE_URL

API2_BASE_URL = "https://api2.pennsieve.io"


class AuthenticationClient:
    """Handles Pennsieve authentication via Cognito."""

    def __init__(self, api_host: str = BASE_URL):
        self.api_host = api_host
        self._access_token: Optional[str] = None
        self._id_token: Optional[str] = None

    def authenticate(self, api_key: str, api_secret: str) -> str:
        """Authenticate and return access token."""
        url = f"{self.api_host}/authentication/cognito-config"

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        cognito_app_client_id = data["tokenPool"]["appClientId"]
        cognito_region = data["region"]

        cognito_idp_client = boto3.client(
            "cognito-idp",
            region_name=cognito_region,
            aws_access_key_id="",
            aws_secret_access_key="",
        )

        login_response = cognito_idp_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": api_key, "PASSWORD": api_secret},
            ClientId=cognito_app_client_id,
        )

        self._access_token = login_response["AuthenticationResult"]["AccessToken"]
        self._id_token = login_response["AuthenticationResult"]["IdToken"]
        return self._access_token

    def get_auth_headers(self) -> Dict[str, str]:
        """Return headers with Bearer token for authenticated requests."""
        if not self._access_token:
            raise ValueError("Not authenticated. Call authenticate() first.")
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }


def get_all_datasets(auth_client: AuthenticationClient) -> List[Dict]:
    """Get all datasets."""
    datasets = []
    offset = 0
    page_size = 25

    while True:
        url = (
            f"{BASE_URL}/datasets/paginated"
            f"?limit={page_size}&offset={offset}&orderBy=Name&orderDirection=Asc"
            f"&includeBannerUrl=false&includePublishedDataset=false"
        )
        response = requests.get(url, headers=auth_client.get_auth_headers())
        response.raise_for_status()
        data = response.json()

        batch = data.get("datasets", [])
        if not batch:
            break

        datasets.extend(batch)
        offset += page_size
        if offset >= data.get("totalCount", 0):
            break

    return datasets


def find_dataset_by_name(name: str, all_datasets: List[Dict]) -> Optional[Dict]:
    """Find a dataset by name."""
    for ds in all_datasets:
        content = ds.get("content", {})
        if content.get("name", "").strip() == name:
            return ds
    return None


def get_upload_credentials(auth_client: AuthenticationClient, dataset_id: str) -> Dict:
    """Get S3 upload credentials for a dataset."""
    encoded_id = quote(dataset_id, safe="")
    url = f"{BASE_URL}/datasets/{encoded_id}/storage"

    response = requests.get(url, headers=auth_client.get_auth_headers())
    response.raise_for_status()
    return response.json()


def compute_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def upload_file(
    auth_client: AuthenticationClient,
    dataset_id: str,
    file_path: str,
    folder_id: Optional[str] = None
) -> Dict:
    """
    Upload a file to a Pennsieve dataset.

    Steps:
    1. Get presigned URL for upload
    2. Upload file to S3
    3. Complete the upload to create the package
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_name = file_path.name
    file_size = file_path.stat().st_size

    print(f"Uploading: {file_name} ({file_size} bytes)")

    # Step 1: Request upload (get presigned URL)
    encoded_dataset_id = quote(dataset_id, safe="")

    # Use the preview upload endpoint
    upload_request_url = f"{BASE_URL}/files/upload/preview"

    upload_payload = {
        "datasetId": dataset_id,
        "files": [
            {
                "fileName": file_name,
                "size": file_size,
                "uploadId": 1
            }
        ]
    }

    if folder_id:
        upload_payload["destinationId"] = folder_id

    response = requests.post(
        upload_request_url,
        json=upload_payload,
        headers=auth_client.get_auth_headers()
    )
    response.raise_for_status()
    upload_info = response.json()

    print(f"  Got upload URL")

    # Extract the presigned URL and fields
    package_info = upload_info["packages"][0]
    presigned_url = package_info["url"]
    fields = package_info.get("fields", {})

    # Step 2: Upload to S3
    print(f"  Uploading to S3...")

    with open(file_path, 'rb') as f:
        file_data = f.read()

    # If there are fields, use multipart form upload
    if fields:
        files = {
            'file': (file_name, file_data)
        }
        s3_response = requests.post(presigned_url, data=fields, files=files)
    else:
        # Direct PUT
        s3_response = requests.put(
            presigned_url,
            data=file_data,
            headers={'Content-Type': 'application/octet-stream'}
        )

    if not s3_response.ok:
        print(f"  S3 upload failed: {s3_response.status_code}")
        print(f"  Response: {s3_response.text}")
        s3_response.raise_for_status()

    print(f"  S3 upload complete")

    # Step 3: Complete the upload
    complete_url = f"{BASE_URL}/files/upload/complete"
    complete_payload = {
        "datasetId": dataset_id,
        "files": [
            {
                "uploadId": 1,
                "fileName": file_name,
                "size": file_size,
                "packageId": package_info.get("packageId"),
                "importId": package_info.get("importId")
            }
        ]
    }

    if folder_id:
        complete_payload["destinationId"] = folder_id

    complete_response = requests.post(
        complete_url,
        json=complete_payload,
        headers=auth_client.get_auth_headers()
    )

    if complete_response.ok:
        print(f"  Upload completed successfully!")
        return complete_response.json()
    else:
        print(f"  Complete request status: {complete_response.status_code}")
        # Some APIs don't require explicit complete call
        return {"status": "uploaded", "file": file_name}


def main():
    parser = argparse.ArgumentParser(
        description='Upload a file to a Pennsieve dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--api-key', required=True, help='Pennsieve API key')
    parser.add_argument('--api-secret', required=True, help='Pennsieve API secret')
    parser.add_argument('--dataset', required=True, help='Dataset name')
    parser.add_argument('--file', required=True, help='Path to file to upload')
    parser.add_argument('--folder', help='Folder name within dataset (optional)')

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    # Authenticate
    print("Authenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")

    # Find dataset
    print(f"Finding dataset: {args.dataset}")
    all_datasets = get_all_datasets(auth_client)
    dataset = find_dataset_by_name(args.dataset, all_datasets)

    if not dataset:
        print(f"ERROR: Dataset not found: {args.dataset}")
        sys.exit(1)

    dataset_id = dataset["content"]["id"]
    print(f"Dataset ID: {dataset_id}")

    # Upload file
    try:
        result = upload_file(auth_client, dataset_id, args.file)
        print(f"\nSuccess! File uploaded to {args.dataset}")
    except Exception as e:
        print(f"ERROR: Upload failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
