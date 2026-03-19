#!/usr/bin/env python3
"""
Delete external publications (DOIs) from Pennsieve datasets.

Usage:
  # Delete DOIs from all datasets
  python delete_publications.py --api-key KEY --api-secret SECRET --all \
      --dois "10.1016/j.example.2025.01.001" "10.1016/j.example.2025.02.002"

  # Delete DOIs from specific datasets
  python delete_publications.py --api-key KEY --api-secret SECRET \
      --datasets "PennEPI00088" "PennEPI00090" \
      --dois "10.1016/j.example.2025.01.001"

  # Dry run
  python delete_publications.py --api-key KEY --api-secret SECRET --all \
      --dois "10.1016/j.example.2025.01.001" --dry-run
"""

import argparse
import sys
from typing import List, Dict, Optional

import requests
import boto3

from helpers import load_data, save_data, BASE_URL


class AuthenticationClient:
    """Handles Pennsieve authentication via Cognito."""

    def __init__(self, api_host: str = BASE_URL):
        self.api_host = api_host
        self._access_token: Optional[str] = None

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


class PublicationDeleter:
    """Deletes external publications (DOIs) from Pennsieve datasets."""

    def __init__(
        self,
        auth_client: AuthenticationClient,
        dry_run: bool = False,
        force_reload: bool = False
    ):
        self.auth_client = auth_client
        self.dry_run = dry_run
        self.force_reload = force_reload

    def get_all_datasets(self) -> List[Dict]:
        """Get all datasets, with caching."""
        datasets = load_data("datasets", force_reload=self.force_reload)
        if datasets is None:
            print("Fetching datasets from network...")
            datasets = self._fetch_all_datasets()
            save_data(datasets, "datasets")
        return datasets

    def _fetch_all_datasets(self) -> List[Dict]:
        """Paginate through all datasets from Pennsieve API."""
        datasets = []
        offset = 0
        page_size = 25

        while True:
            url = (
                f"{BASE_URL}/datasets/paginated"
                f"?limit={page_size}&offset={offset}&orderBy=Name&orderDirection=Asc"
                f"&includeBannerUrl=false&includePublishedDataset=false"
            )
            response = requests.get(url, headers=self.auth_client.get_auth_headers())
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

    def find_dataset_by_name(self, name: str, all_datasets: List[Dict]) -> Optional[Dict]:
        """Find a dataset by name."""
        for ds in all_datasets:
            content = ds.get("content", {})
            if content.get("name", "").strip() == name:
                return ds
        return None

    def delete_publication(
        self,
        dataset_id: str,
        dataset_name: str,
        doi: str,
        relationship_type: str
    ) -> bool:
        """Delete a single external publication from a dataset."""
        print(f"  Deleting DOI: {doi}")

        if self.dry_run:
            print(f"    [DRY-RUN] Would delete publication")
            return True

        url = (
            f"{BASE_URL}/datasets/{dataset_id}/external-publications"
            f"?doi={doi}&relationshipType={relationship_type}"
        )

        try:
            response = requests.delete(
                url,
                headers=self.auth_client.get_auth_headers()
            )
            # 404 is OK - means it wasn't there
            if response.status_code == 404:
                print(f"    Not found (OK)")
                return True
            response.raise_for_status()
            print(f"    Deleted successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"    Status: {e.response.status_code}")
                print(f"    Response: {e.response.text}")
            return False

    def run(
        self,
        dataset_names: Optional[List[str]] = None,
        all_datasets_flag: bool = False,
        dois: List[str] = None,
        relationship_type: str = "IsDescribedBy"
    ) -> tuple:
        """
        Main entry point.

        Returns:
            Tuple of (total_datasets, success_count, failure_count)
        """
        if not dataset_names and not all_datasets_flag:
            raise ValueError("Must provide either --datasets or --all")

        if not dois:
            raise ValueError("Must provide at least one DOI with --dois")

        print("=" * 60)
        print("PUBLICATION DELETER")
        print("=" * 60)
        print(f"DOIs to delete: {len(dois)}")
        for doi in dois:
            print(f"  - {doi}")
        print(f"Relationship type: {relationship_type}")
        print(f"Dry run: {self.dry_run}")
        print("=" * 60)

        # Get all datasets
        all_datasets = self.get_all_datasets()
        print(f"Total datasets available: {len(all_datasets)}")

        # Filter datasets
        datasets_to_process = []
        if all_datasets_flag:
            datasets_to_process = all_datasets
        else:
            for name in dataset_names:
                ds = self.find_dataset_by_name(name, all_datasets)
                if ds:
                    datasets_to_process.append(ds)
                else:
                    print(f"WARNING: Dataset not found: {name}")

        if not datasets_to_process:
            print("No datasets to process")
            return (0, 0, 0)

        print(f"Datasets to process: {len(datasets_to_process)}")

        success_count = 0
        failure_count = 0

        for ds in datasets_to_process:
            dataset_id = ds.get("content", {}).get("id")
            dataset_name = ds.get("content", {}).get("name", "Unknown")

            if not dataset_id:
                print(f"  SKIPPING: {dataset_name} - no ID found")
                failure_count += 1
                continue

            print(f"\nProcessing: {dataset_name}")
            dataset_success = True

            for doi in dois:
                if not self.delete_publication(dataset_id, dataset_name, doi, relationship_type):
                    dataset_success = False

            if dataset_success:
                success_count += 1
            else:
                failure_count += 1

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total datasets: {len(datasets_to_process)}")
        print(f"Succeeded: {success_count}")
        print(f"Failed: {failure_count}")

        if self.dry_run:
            print("\n[DRY-RUN MODE] No actual changes were made")

        return (len(datasets_to_process), success_count, failure_count)


def main():
    parser = argparse.ArgumentParser(
        description='Delete external publications (DOIs) from Pennsieve datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete DOIs from all datasets
  %(prog)s --api-key KEY --api-secret SECRET --all \\
      --dois "10.1016/j.other.2025.01.001" "10.1016/j.third.2025.02.002"

  # Delete DOIs from specific datasets
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets "PennEPI00088" "PennEPI00090" \\
      --dois "10.1016/j.example.2025.01.001"

  # Dry run to preview changes
  %(prog)s --api-key KEY --api-secret SECRET --all \\
      --dois "10.1016/j.example.2025.01.001" --dry-run
        """
    )

    # Authentication
    parser.add_argument('--api-key', required=True, help='Pennsieve API key')
    parser.add_argument('--api-secret', required=True, help='Pennsieve API secret')

    # Dataset selection
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument('--datasets', nargs='+', help='Dataset names to process')
    dataset_group.add_argument('--all', action='store_true', dest='all_datasets', help='Process all datasets')

    # Publication options
    parser.add_argument(
        '--dois',
        nargs='+',
        required=True,
        help='DOI(s) to delete from each dataset'
    )
    parser.add_argument(
        '--relationship-type',
        default='IsDescribedBy',
        help='DataCite relationship type (default: IsDescribedBy)'
    )

    # Options
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--force-reload', action='store_true', help='Bypass cache')

    args = parser.parse_args()

    # Authenticate
    print("Authenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")

    # Create deleter and run
    deleter = PublicationDeleter(
        auth_client=auth_client,
        dry_run=args.dry_run,
        force_reload=args.force_reload
    )

    total, success, failures = deleter.run(
        dataset_names=args.datasets,
        all_datasets_flag=args.all_datasets,
        dois=args.dois,
        relationship_type=args.relationship_type
    )

    # Exit code
    if failures > 0:
        sys.exit(1)
    if total == 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
