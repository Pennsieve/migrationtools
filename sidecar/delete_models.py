#!/usr/bin/env python3
"""
Delete Models Script

Deletes all models (and their records) from Pennsieve datasets.

Usage:
  # Dry run for a single dataset
  python delete_models.py --api-key KEY --api-secret SECRET \
      --datasets PennEPI00949 --dry-run

  # Delete all models from all PennEPI datasets
  python delete_models.py --api-key KEY --api-secret SECRET \
      --prefix PennEPI --execute

  # Delete specific models only
  python delete_models.py --api-key KEY --api-secret SECRET \
      --datasets PennEPI00949 --models person eeg --execute
"""

import argparse
import sys
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

import requests
import boto3

from helpers import (
    load_data,
    save_data,
    BASE_URL,
)

API2_BASE_URL = "https://api2.pennsieve.io"


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

    @property
    def access_token(self) -> Optional[str]:
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


class ModelDeleter:
    """Deletes models from Pennsieve datasets."""

    def __init__(
        self,
        auth_client: AuthenticationClient,
        dry_run: bool = True,
        force_reload: bool = False,
        verbose: bool = False
    ):
        self.auth_client = auth_client
        self.dry_run = dry_run
        self.force_reload = force_reload
        self.verbose = verbose

    def _log(self, message: str, indent: int = 0):
        """Print log message with optional indentation."""
        prefix = "  " * indent
        print(f"{prefix}{message}")

    def _debug(self, message: str, indent: int = 0):
        """Print debug message if verbose mode is on."""
        if self.verbose:
            self._log(f"[DEBUG] {message}", indent)

    # -------------------------------------------------------------------------
    # Dataset Helpers
    # -------------------------------------------------------------------------

    def get_all_datasets(self) -> List[Dict]:
        """Get all datasets, with caching."""
        datasets = load_data("datasets", force_reload=self.force_reload)
        if datasets is None:
            self._log("Fetching datasets from network...")
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

    # -------------------------------------------------------------------------
    # Model Operations
    # -------------------------------------------------------------------------

    def get_models_for_dataset(self, dataset_id: str) -> List[Dict]:
        """Get all models for a dataset."""
        encoded_dataset_id = quote(dataset_id, safe="")
        url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded_dataset_id}"

        response = requests.get(url, headers=self.auth_client.get_auth_headers())
        response.raise_for_status()

        return response.json()

    def delete_model(self, model_id: str, dataset_id: str, force: bool = True) -> bool:
        """Delete a model from a dataset."""
        encoded_dataset_id = quote(dataset_id, safe="")
        force_param = "true" if force else "false"
        url = f"{API2_BASE_URL}/metadata/models/{model_id}?dataset_id={encoded_dataset_id}&force={force_param}"

        self._debug(f"DELETE {url}", indent=3)

        if self.dry_run:
            return True

        response = requests.delete(url, headers=self.auth_client.get_auth_headers())

        if not response.ok:
            self._log(f"ERROR deleting model: {response.status_code}", indent=3)
            self._log(f"Response: {response.text}", indent=3)
            return False

        return True

    # -------------------------------------------------------------------------
    # Main Processing
    # -------------------------------------------------------------------------

    def process_dataset(
        self,
        dataset_name: str,
        all_datasets: List[Dict],
        model_filter: Optional[List[str]] = None
    ) -> Tuple[int, int]:
        """
        Process a single dataset - delete all (or filtered) models.

        Args:
            dataset_name: Name of the dataset
            all_datasets: List of all datasets
            model_filter: Optional list of model names to delete (None = all)

        Returns:
            Tuple of (success_count, failure_count)
        """
        self._log(f"\n{'='*60}")
        self._log(f"Processing dataset: {dataset_name}")
        self._log(f"{'='*60}")

        # Find dataset
        dataset = self.find_dataset_by_name(dataset_name, all_datasets)
        if not dataset:
            self._log(f"ERROR: Dataset not found: {dataset_name}", indent=1)
            return (0, 0)

        dataset_id = dataset.get("content", {}).get("id")
        if not dataset_id:
            self._log(f"ERROR: Could not get dataset ID", indent=1)
            return (0, 0)

        self._log(f"Dataset ID: {dataset_id}", indent=1)

        # Get models
        models = self.get_models_for_dataset(dataset_id)
        self._log(f"Found {len(models)} models", indent=1)

        if not models:
            self._log("No models to delete", indent=1)
            return (0, 0)

        success_count = 0
        failure_count = 0

        for item in models:
            model = item.get("model", {})
            model_id = model.get("id")
            model_name = model.get("name", "unknown")

            # Apply filter if specified
            if model_filter and model_name not in model_filter:
                self._debug(f"Skipping model '{model_name}' (not in filter)", indent=2)
                continue

            self._log(f"Deleting model: {model_name} (ID: {model_id})", indent=2)

            if self.dry_run:
                self._log(f"[DRY-RUN] Would delete model: {model_name}", indent=3)
                success_count += 1
            else:
                if self.delete_model(model_id, dataset_id, force=True):
                    self._log(f"Deleted successfully", indent=3)
                    success_count += 1
                else:
                    failure_count += 1

        return (success_count, failure_count)

    def run(
        self,
        dataset_names: Optional[List[str]] = None,
        dataset_prefix: Optional[str] = None,
        model_filter: Optional[List[str]] = None
    ) -> Tuple[int, int, int]:
        """
        Main entry point for processing.

        Args:
            dataset_names: Explicit list of dataset names
            dataset_prefix: Prefix to match dataset names
            model_filter: Optional list of model names to delete (None = all)

        Returns:
            Tuple of (datasets_processed, total_success, total_failures)
        """
        if not dataset_names and not dataset_prefix:
            raise ValueError("Must provide either dataset_names or dataset_prefix")

        self._log("="*60)
        self._log("MODEL DELETER")
        self._log("="*60)
        self._log(f"Model filter: {model_filter or 'ALL MODELS'}")
        self._log(f"Dry run: {self.dry_run}")
        self._log("="*60)

        if not self.dry_run:
            self._log("")
            self._log("WARNING: This will permanently delete models and their records!")
            self._log("")

        # Get all datasets
        all_datasets = self.get_all_datasets()
        self._log(f"Total datasets available: {len(all_datasets)}")

        # Filter datasets
        datasets_to_process = []
        for ds in all_datasets:
            ds_name = ds.get("content", {}).get("name", "")
            if dataset_names and ds_name in dataset_names:
                datasets_to_process.append(ds_name)
            elif dataset_prefix and ds_name.startswith(dataset_prefix):
                datasets_to_process.append(ds_name)

        if not datasets_to_process:
            self._log("No datasets matched the criteria")
            return (0, 0, 0)

        self._log(f"Datasets to process: {len(datasets_to_process)}")

        total_success = 0
        total_failures = 0

        for ds_name in datasets_to_process:
            success, failures = self.process_dataset(
                ds_name, all_datasets, model_filter
            )
            total_success += success
            total_failures += failures

        # Summary
        self._log(f"\n{'='*60}")
        self._log("SUMMARY")
        self._log(f"{'='*60}")
        self._log(f"Datasets processed: {len(datasets_to_process)}")
        self._log(f"Models deleted: {total_success}")
        self._log(f"Failures: {total_failures}")

        if self.dry_run:
            self._log("\n[DRY-RUN MODE] No actual changes were made")
            self._log("Run with --execute to actually delete models")

        return (len(datasets_to_process), total_success, total_failures)


def main():
    parser = argparse.ArgumentParser(
        description='Delete models from Pennsieve datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview) for a single dataset
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00949 --dry-run

  # Delete all models from all PennEPI datasets
  %(prog)s --api-key KEY --api-secret SECRET \\
      --prefix PennEPI --execute

  # Delete specific models only
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00949 --models person eeg mri --execute
        """
    )

    # Authentication
    parser.add_argument('--api-key', required=True, help='Pennsieve API key')
    parser.add_argument('--api-secret', required=True, help='Pennsieve API secret')

    # Dataset selection
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        '--datasets', nargs='+', metavar='NAME',
        help='Explicit list of dataset names'
    )
    dataset_group.add_argument(
        '--prefix', metavar='PREFIX',
        help='Process datasets starting with this prefix'
    )

    # Model selection
    parser.add_argument(
        '--models', nargs='+', metavar='MODEL',
        help='Specific models to delete (default: all models)'
    )

    # Execution mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--dry-run', action='store_true',
        help='Preview what would be deleted without making changes'
    )
    mode_group.add_argument(
        '--execute', action='store_true',
        help='Actually delete the models (DESTRUCTIVE)'
    )

    # Options
    parser.add_argument('--force-reload', action='store_true', help='Bypass cache')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Authenticate
    print("Authenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")

    # Create deleter and run
    deleter = ModelDeleter(
        auth_client=auth_client,
        dry_run=args.dry_run,
        force_reload=args.force_reload,
        verbose=args.verbose
    )

    datasets_processed, success, failures = deleter.run(
        dataset_names=args.datasets,
        dataset_prefix=args.prefix,
        model_filter=args.models
    )

    # Exit code
    if failures > 0:
        sys.exit(1)
    if datasets_processed == 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
