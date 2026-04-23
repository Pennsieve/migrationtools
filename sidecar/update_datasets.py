#!/usr/bin/env python3
"""
Flexible Pennsieve Dataset Updater

Updates metadata, contributors, owner, and readme for datasets.
Authenticates using API key + secret to get a token.
"""

import argparse
import json
import logging
import os
import sys
from typing import List, Optional, Dict

import boto3
import requests

from helpers import get_all_datasets, load_data, save_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PennsieveAuth:
    """Handle Pennsieve authentication via Cognito"""

    def __init__(self, api_host: str = "https://api.pennsieve.io"):
        self.api_host = api_host

    def get_token(self, api_key: str, api_secret: str) -> str:
        """
        Authenticate with API key + secret and return access token.

        Args:
            api_key: Pennsieve API key (used as username)
            api_secret: Pennsieve API secret (used as password)

        Returns:
            Access token string
        """
        url = f"{self.api_host}/authentication/cognito-config"

        try:
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

            access_token = login_response["AuthenticationResult"]["AccessToken"]
            logger.info("Successfully authenticated")
            return access_token

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise


class DatasetUpdater:
    """Update Pennsieve datasets with flexible options"""

    def __init__(self, token: str, api_host: str = "https://api.pennsieve.io", dry_run: bool = False, force_reload: bool = False):
        self.token = token
        self.api_host = api_host
        self.dry_run = dry_run
        self.force_reload = force_reload
        self.headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        self._datasets_cache = None

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling. Returns dict, empty dict for no-content success, or None for failure."""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            # Return empty dict for successful requests with no body (e.g., 204 No Content)
            if not response.text or response.text.strip() == "":
                return {}
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"  API request failed: {method} {url}")
            logger.error(f"  Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"  Status: {e.response.status_code}")
                logger.error(f"  Response: {e.response.text}")
            return None

    def _fetch_all_datasets(self) -> List[Dict]:
        """Fetch all datasets using authenticated token with pagination"""
        datasets = []
        offset = 0
        page_size = 25

        logger.info("Fetching datasets from network...")

        while True:
            url = (
                f"{self.api_host}/datasets/paginated"
                f"?limit={page_size}&offset={offset}&orderBy=Name&orderDirection=Asc"
                f"&includeBannerUrl=false&includePublishedDataset=false"
            )
            result = self._make_request("GET", url)

            if not result:
                break

            batch = result.get("datasets", [])
            if not batch:
                break

            datasets.extend(batch)
            offset += page_size
            if offset >= result.get("totalCount", 0):
                break

        logger.info(f"Fetched {len(datasets)} datasets")
        return datasets

    def find_dataset_by_name(self, dataset_name: str) -> Optional[Dict]:
        """Find a dataset by name using authenticated requests"""
        # Use in-memory cache if available and not forcing reload
        if self._datasets_cache is None or self.force_reload:
            self._datasets_cache = self._fetch_all_datasets()
            self.force_reload = False  # Only force reload once

        for ds in self._datasets_cache:
            if ds.get("content", {}).get("name") == dataset_name:
                return ds

        # Not found - show available datasets for debugging
        available = [ds.get("content", {}).get("name", "?") for ds in self._datasets_cache[:10]]
        logger.error(f"  Available datasets (first 10): {available}")
        if len(self._datasets_cache) > 10:
            logger.error(f"  ... and {len(self._datasets_cache) - 10} more")

        return None

    def update_contributors(self, dataset_id: str, contributor_ids: List[int],
                           remove_contributor_id: Optional[int] = None) -> bool:
        """
        Update dataset contributors.

        Args:
            dataset_id: Dataset node ID
            contributor_ids: List of contributor IDs to add
            remove_contributor_id: Optional contributor ID to remove first
        """
        logger.info(f"Updating contributors for dataset {dataset_id}")

        if self.dry_run:
            if remove_contributor_id:
                logger.info(f"  [DRY RUN] Would remove contributor {remove_contributor_id}")
            logger.info(f"  [DRY RUN] Would add contributors: {contributor_ids}")
            return True

        # Remove contributor if specified
        if remove_contributor_id:
            delete_url = f"{self.api_host}/datasets/{dataset_id}/contributors/{remove_contributor_id}"
            logger.info(f"  Removing contributor {remove_contributor_id}...")

            try:
                response = requests.delete(delete_url, headers=self.headers)
                if response.status_code == 404:
                    logger.info(f"    Contributor {remove_contributor_id} not found (OK)")
                elif response.status_code in [200, 204]:
                    logger.info(f"    Removed contributor {remove_contributor_id}")
                else:
                    logger.warning(f"    Unexpected status {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"    Error deleting contributor: {e}")

        # Add contributors
        success = True
        for contributor_id in contributor_ids:
            url = f"{self.api_host}/datasets/{dataset_id}/contributors"
            payload = {"contributorId": contributor_id}

            logger.info(f"  Adding contributor {contributor_id}...")
            result = self._make_request("PUT", url, json=payload)

            if result is None:
                logger.error(f"    Failed to add contributor {contributor_id}")
                success = False
            else:
                logger.info(f"    Added contributor {contributor_id}")

        return success

    def update_description(self, dataset_id: str, description: str) -> bool:
        """Update dataset description only"""
        logger.info(f"Updating description for dataset {dataset_id}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would update description to: {description[:50]}...")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}"
        payload = {"description": description}

        result = self._make_request("PUT", url, json=payload)
        if result:
            logger.info("  Updated description successfully")
            return True
        return False

    def update_tags(self, dataset_id: str, tags: List[str]) -> bool:
        """Update dataset tags only"""
        logger.info(f"Updating tags for dataset {dataset_id}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would update tags to: {tags}")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}"
        payload = {"tags": tags}

        result = self._make_request("PUT", url, json=payload)
        if result:
            logger.info("  Updated tags successfully")
            return True
        return False

    def update_readme(self, dataset_id: str, readme_text: str) -> bool:
        """Update dataset readme"""
        logger.info(f"Updating readme for dataset {dataset_id}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would update readme to: {readme_text[:50]}...")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}/readme"
        payload = {"readme": readme_text}

        result = self._make_request("PUT", url, json=payload)
        if result is not None:
            logger.info("  Updated readme successfully")
            return True
        return False

    def update_owner(self, dataset_id: str, owner_id: str) -> bool:
        """Update dataset owner"""
        logger.info(f"Updating owner for dataset {dataset_id}")
        logger.info(f"  New owner: {owner_id}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would set owner to: {owner_id}")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}/collaborators/owner"
        payload = {
            "id": owner_id,
            "role": "owner"
        }

        logger.debug(f"  PUT {url}")
        logger.debug(f"  Payload: {payload}")

        result = self._make_request("PUT", url, json=payload)
        if result is not None:
            logger.info(f"  SUCCESS: Updated owner to {owner_id}")
            return True
        else:
            logger.error(f"  FAILED: Could not update owner")
            return False

    def add_team(self, dataset_id: str, team_id: str, role: str = "manager") -> bool:
        """Add a team as collaborator to a dataset"""
        logger.info(f"Adding team to dataset {dataset_id}")
        logger.info(f"  Team: {team_id}, Role: {role}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would add team {team_id} as {role}")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}/collaborators/teams"
        payload = {
            "id": team_id,
            "role": role
        }

        result = self._make_request("PUT", url, json=payload)
        if result is not None:
            logger.info(f"  SUCCESS: Added team {team_id} as {role}")
            return True
        else:
            logger.error(f"  FAILED: Could not add team")
            return False

    def update_banner(self, dataset_id: str, image_path: str) -> bool:
        """Update dataset banner image"""
        logger.info(f"Updating banner for dataset {dataset_id}")

        if not os.path.exists(image_path):
            logger.error(f"  Banner file not found: {image_path}")
            return False

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would upload banner from: {image_path}")
            return True

        url = f"{self.api_host}/datasets/{dataset_id}/banner"

        try:
            with open(image_path, "rb") as img_file:
                # Determine content type from extension
                ext = os.path.splitext(image_path)[1].lower()
                content_type = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif"
                }.get(ext, "image/png")

                files = {"banner": (os.path.basename(image_path), img_file, content_type)}
                # Use requests directly since we need multipart form data
                response = requests.put(url, headers={"Authorization": f"Bearer {self.token}"}, files=files)
                response.raise_for_status()

            logger.info(f"  Updated banner successfully")
            return True
        except requests.RequestException as e:
            logger.error(f"  Failed to update banner: {e}")
            return False

    def process_dataset(self, dataset_name: str,
                       description: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       readme_text: Optional[str] = None,
                       contributor_ids: Optional[List[int]] = None,
                       remove_contributor_id: Optional[int] = None,
                       owner_id: Optional[str] = None,
                       team_id: Optional[str] = None,
                       team_role: str = "manager",
                       banner_path: Optional[str] = None,
                       skip_lookup: bool = False) -> bool:
        """
        Process a single dataset with specified updates.
        Each option is independent - only updates what's explicitly provided.

        Args:
            dataset_name: Name of the dataset
            description: Optional new description
            tags: Optional list of tags
            readme_text: Optional readme text
            contributor_ids: Optional list of contributor IDs to add
            remove_contributor_id: Optional contributor ID to remove
            owner_id: Optional new owner user ID
            team_id: Optional team ID to add as collaborator
            team_role: Role for the team (viewer, editor, manager)
            banner_path: Optional path to banner image file
            skip_lookup: If True, treat dataset_name as a dataset ID and skip fetching datasets
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing dataset: {dataset_name}")
        logger.info(f"{'='*60}")

        if skip_lookup:
            dataset_id = dataset_name
            logger.info(f"Skipping dataset lookup; using provided dataset ID: {dataset_id}")
        else:
            # Find dataset
            dataset = self.find_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"Dataset not found: {dataset_name}")
                return False

            dataset_id = dataset.get("content", {}).get("id")
            logger.info(f"Dataset ID: {dataset_id}")

        success = True
        actions_taken = 0

        # Update description if provided (separate call)
        if description is not None:
            if not self.update_description(dataset_id, description):
                success = False
            actions_taken += 1

        # Update tags if provided (separate call)
        if tags is not None:
            if not self.update_tags(dataset_id, tags):
                success = False
            actions_taken += 1

        # Update readme if provided
        if readme_text is not None:
            if not self.update_readme(dataset_id, readme_text):
                success = False
            actions_taken += 1

        # Update contributors if provided
        if contributor_ids is not None:
            if not self.update_contributors(dataset_id, contributor_ids, remove_contributor_id):
                success = False
            actions_taken += 1

        # Update owner if provided
        if owner_id is not None:
            if not self.update_owner(dataset_id, owner_id):
                success = False
            actions_taken += 1

        # Add team if provided
        if team_id is not None:
            if not self.add_team(dataset_id, team_id, team_role):
                success = False
            actions_taken += 1

        # Update banner if provided
        if banner_path is not None:
            if not self.update_banner(dataset_id, banner_path):
                success = False
            actions_taken += 1

        if actions_taken == 0:
            logger.info("  No update actions specified for this dataset")

        return success


def main():
    parser = argparse.ArgumentParser(
        description='Flexible Pennsieve dataset updater',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with all options
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00088 PennEPI00090 \\
      --description "My dataset description" \\
      --tags epilepsy research \\
      --readme "This is the readme text" \\
      --contributors 32 31 18 \\
      --remove-contributor 19 \\
      --owner "N:user:xxxx-xxxx" \\
      --dry-run

  # Update just metadata for specific datasets
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets MyDataset1 MyDataset2 \\
      --description "New description" \\
      --tags tag1 tag2 tag3

  # Change owner only
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets MyDataset \\
      --owner "N:user:xxxx-xxxx"

  # Change owner for all PennEPI datasets
  %(prog)s --api-key KEY --api-secret SECRET \\
      --prefix PennEPI \\
      --owner "N:user:xxxx-xxxx"
        """
    )

    # Authentication
    parser.add_argument('--api-key', required=True, help='Pennsieve API key')
    parser.add_argument('--api-secret', required=True, help='Pennsieve API secret')
    parser.add_argument('--api-host', default='https://api.pennsieve.io', help='API host URL')

    # Dataset selection
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument('--datasets', nargs='+', help='Dataset names to process')
    dataset_group.add_argument('--prefix', metavar='PREFIX', help='Process datasets starting with this prefix')
    dataset_group.add_argument('--all', action='store_true', dest='all_datasets', help='Process all datasets in workspace')

    # Metadata options
    parser.add_argument('--description', help='Dataset description')
    parser.add_argument('--tags', nargs='+', help='Dataset tags')
    parser.add_argument('--readme', help='Dataset readme text')

    # Contributor options
    parser.add_argument('--contributors', nargs='+', type=int, help='Contributor IDs to add')
    parser.add_argument('--remove-contributor', type=int, help='Contributor ID to remove')

    # Owner option
    parser.add_argument('--owner', help='New owner user ID (e.g., N:user:xxxx-xxxx)')

    # Team option
    parser.add_argument('--team', help='Team ID to add as collaborator (e.g., N:team:xxxx-xxxx)')
    parser.add_argument('--team-role', default='manager', choices=['viewer', 'editor', 'manager'], help='Role for team (default: manager)')
    parser.add_argument('--skip-lookup', action='store_true', help='Skip GET /datasets/paginated and treat --datasets values as dataset IDs')

    # Banner option
    parser.add_argument('--banner', help='Path to banner image file (png, jpg, gif)')

    # Execution options
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--force-reload', action='store_true', help='Force fresh fetch of datasets (bypass any caching)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Warn if no update options provided
    if not any([args.description, args.tags, args.readme, args.contributors, args.owner, args.banner, args.team]):
        logger.warning("No update options provided - will authenticate but take no actions")

    if args.dry_run:
        logger.info("\n" + "="*60)
        logger.info("DRY RUN MODE - No actual changes will be made")
        logger.info("="*60)

    # Authenticate
    logger.info("Authenticating...")
    auth = PennsieveAuth(args.api_host)
    try:
        token = auth.get_token(args.api_key, args.api_secret)
    except Exception as e:
        logger.error(f"Failed to authenticate: {e}")
        sys.exit(1)

    # Initialize updater
    updater = DatasetUpdater(token, args.api_host, dry_run=args.dry_run, force_reload=args.force_reload)

    # Get dataset names to process
    if args.datasets:
        dataset_names = args.datasets
    else:
        logger.info("Fetching all datasets...")
        all_datasets = updater._fetch_all_datasets()
        if args.prefix:
            dataset_names = [
                ds.get("content", {}).get("name")
                for ds in all_datasets
                if ds.get("content", {}).get("name", "").startswith(args.prefix)
            ]
            logger.info(f"Found {len(dataset_names)} datasets matching prefix '{args.prefix}'")
        else:
            dataset_names = [ds.get("content", {}).get("name") for ds in all_datasets if ds.get("content", {}).get("name")]
            logger.info(f"Found {len(dataset_names)} datasets to process")

    # Process datasets
    total = len(dataset_names)
    succeeded = 0
    failed = 0

    for dataset_name in dataset_names:
        if updater.process_dataset(
            dataset_name,
            description=args.description,
            tags=args.tags,
            readme_text=args.readme,
            contributor_ids=args.contributors,
            remove_contributor_id=args.remove_contributor,
            owner_id=args.owner,
            team_id=args.team,
            team_role=args.team_role,
            banner_path=args.banner,
            skip_lookup=args.skip_lookup
        ):
            succeeded += 1
        else:
            failed += 1

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total datasets: {total}")
    logger.info(f"Succeeded: {succeeded}")
    logger.info(f"Failed: {failed}")

    if args.dry_run:
        logger.info("\n(Dry-run mode: no actual changes were made)")

    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
