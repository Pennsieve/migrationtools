#!/usr/bin/env python3
"""
Model Populator Script

Creates a model from a template and populates it with records from files on Pennsieve.

Usage:
  # Process specific datasets with a file pattern (single model)
  python model_populator.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00086 PennEPI00087 \\
      --file-pattern _ieeg.json \\
      --template-id TEMPLATE_UUID \\
      --model-name bids_ieeg_sidecar --display-name "BIDS iEEG sidecar"

  # Process multiple models using a config file
  python model_populator.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00014 PennEPI00007 \\
      --config models_config.json

  # Use existing model (skip creation)
  python model_populator.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00102 \\
      --file-pattern participants.json \\
      --model-id EXISTING_MODEL_UUID

  # Dry run (preview what would happen)
  python model_populator.py --api-key KEY --api-secret SECRET --all \\
      --config models_config.json --dry-run

Config file format (models_config.json):
  {
    "models": [
      {
        "template_id": "uuid-here",
        "model_name": "pennepi_participants",
        "display_name": "PennEPI Participants",
        "file_pattern": "participants.json"
      },
      {
        "template_id": "uuid-here",
        "model_name": "penn_epi_dataset_description",
        "display_name": "Penn EPI Dataset Description",
        "file_pattern": "dataset_description.json"
      }
    ]
  }
"""

import argparse
import csv
import io
import json
import sys
import requests
import boto3
from typing import List, Dict, Any, Optional

from urllib.parse import quote

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


PAGE_SIZE = 25


def get_all_datasets(auth_client: AuthenticationClient) -> List[Dict]:
    """Paginate through all datasets from Pennsieve API using Bearer auth."""
    datasets = []
    offset = 0

    while True:
        url = (
            f"{BASE_URL}/datasets/paginated"
            f"?limit={PAGE_SIZE}&offset={offset}&orderBy=Name&orderDirection=Asc"
            f"&includeBannerUrl=false&includePublishedDataset=false"
        )
        response = requests.get(url, headers=auth_client.get_auth_headers())
        response.raise_for_status()
        data = response.json()

        batch = data.get("datasets", [])
        if not batch:
            break

        datasets.extend(batch)
        offset += PAGE_SIZE
        if offset >= data.get("totalCount", 0):
            break

    return datasets


def get_dataset_packages(auth_client: AuthenticationClient, dataset_id: str) -> List[Dict]:
    """Return all packages for a dataset using Bearer auth, handling pagination."""
    encoded_id = quote(dataset_id, safe="")
    base_url = f"{BASE_URL}/datasets/{encoded_id}/packages?pageSize=1000&includeSourceFiles=false"

    all_packages = []
    cursor = None

    while True:
        url = f"{base_url}&cursor={cursor}" if cursor else base_url
        response = requests.get(url, headers=auth_client.get_auth_headers())
        response.raise_for_status()

        data = response.json()
        all_packages.extend(data.get('packages', []))

        cursor = data.get('cursor')
        if not cursor:
            break

    return all_packages


def find_dataset_by_name(dataset_name: str, all_datasets: List[Dict]) -> Optional[Dict]:
    """Find a dataset by name from the list of all datasets."""
    for ds in all_datasets:
        content = ds.get("content", {})
        if content.get("name", "").strip() == dataset_name:
            return ds
    return None


def get_existing_model_by_name(
    auth_client: AuthenticationClient,
    dataset_id: str,
    model_name: str
) -> Optional[str]:
    """
    Find an existing model by name in a dataset.

    GET https://api2.pennsieve.io/metadata/models?dataset_id={DATASET_ID}

    Returns:
        The model ID if found, None otherwise
    """
    encoded_dataset_id = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded_dataset_id}"

    response = requests.get(url, headers=auth_client.get_auth_headers())
    response.raise_for_status()

    models = response.json()
    for item in models:
        model = item.get("model", {})
        if model.get("name") == model_name:
            return model.get("id")

    return None


def create_model_from_template(
    auth_client: AuthenticationClient,
    template_id: str,
    dataset_id: str,
    model_name: str,
    display_name: str,
    description: str = "",
    dry_run: bool = False
) -> Optional[str]:
    """
    Create a model based off a template, or return existing model ID if it already exists.

    POST https://api2.pennsieve.io/metadata/templates/{TEMPLATE_ID}/models?dataset_id={DATASET_ID}

    Omitting the version parameter uses the latest template version.
    Omitting description in the payload falls back to the template's description.

    Payload:
        {"name": "...", "display_name": "..."}

    Returns:
        The model ID from the response, or "dry-run-model-id" if dry run
    """
    encoded_dataset_id = quote(dataset_id, safe="")
    url = (
        f"{API2_BASE_URL}/metadata/templates/{template_id}/models"
        f"?dataset_id={encoded_dataset_id}"
    )
    payload = {
        "name": model_name,
        "display_name": display_name,
    }
    if description:
        payload["description"] = description

    print(f"    URL: {url}")
    print(f"    Payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        print(f"    [DRY-RUN] Would POST")
        return "dry-run-model-id"

    response = requests.post(url, json=payload, headers=auth_client.get_auth_headers())

    # Check for duplicate model name error - find existing model instead
    if response.status_code == 400:
        try:
            error_body = response.json()
            if "duplicate model name" in error_body.get("message", ""):
                print(f"    Model already exists, finding existing model ID...")
                existing_id = get_existing_model_by_name(auth_client, dataset_id, model_name)
                if existing_id:
                    print(f"    Found existing model (ID: {existing_id})")
                    return existing_id
                else:
                    print(f"    ERROR: Could not find existing model by name: {model_name}")
                    response.raise_for_status()
        except json.JSONDecodeError:
            pass

    if not response.ok:
        print(f"    Response status: {response.status_code}")
        print(f"    Response body: {response.text}")
    response.raise_for_status()

    result = response.json()
    model_id = result.get("model", {}).get("id")

    if not model_id:
        raise ValueError(f"Could not extract model ID from response: {result}")

    print(f"    Model created successfully (ID: {model_id})")
    return model_id


def get_package_path(package: Dict, all_packages: List[Dict]) -> str:
    """
    Reconstruct the path to a package by walking up parent IDs.
    Returns path like 'ieeg/subfolder' or '' for root-level packages.
    """
    # Build a lookup of package ID -> package info
    # Note: parentId is the numeric 'id' field, not 'nodeId'
    pkg_lookup = {}
    for pkg in all_packages:
        content = pkg.get("content", {})
        pkg_id = content.get("id")
        if pkg_id:
            pkg_lookup[pkg_id] = pkg

    # Walk up the parent chain
    path_parts = []
    current = package

    while True:
        content = current.get("content", {})
        parent_id = content.get("parentId")

        if not parent_id or parent_id not in pkg_lookup:
            break

        parent = pkg_lookup[parent_id]
        parent_content = parent.get("content", {})
        parent_name = parent_content.get("name", "")

        if parent_name:
            path_parts.insert(0, parent_name)

        current = parent

    return "/".join(path_parts)


def find_target_file(packages: List[Dict], filename_pattern: str, debug: bool = False) -> Optional[Dict]:
    """
    Find the target file package in the dataset by matching a filename pattern.

    The pattern matches if the filename ends with the pattern.
    E.g., pattern '_ieeg.json' matches 'sub-001_ieeg.json'

    Args:
        packages: List of all packages in the dataset
        filename_pattern: The filename pattern to match (e.g., '_ieeg.json')
        debug: If True, print potential matches

    Returns:
        The package dict if found, None otherwise
    """
    potential_matches = []

    for pkg in packages:
        content = pkg.get("content", {})
        name = content.get("name", "")

        # Skip deleted files
        if name.startswith("__DELETED__"):
            continue

        # Skip files in archive folders
        pkg_path = get_package_path(pkg, packages)
        if "archive" in pkg_path.lower():
            continue

        # Match if name equals pattern or ends with pattern
        if name == filename_pattern or name.endswith(filename_pattern):
            return pkg
        # Track potential matches for debugging
        if debug and filename_pattern.split('.')[-1] in name:
            potential_matches.append(name)

    # If no match found and debug mode, show potential matches
    if debug and potential_matches:
        print(f"    DEBUG: No exact match. Similar files found:")
        for match in potential_matches[:10]:  # Show first 10
            print(f"      - {match}")

    return None


def download_file_content(auth_client: AuthenticationClient, node_id: str) -> str:
    """
    Download file content from Pennsieve using the download-manifest endpoint.

    Args:
        auth_client: Authenticated client
        node_id: The nodeId of the package to download

    Returns:
        The file content as a string
    """
    manifest_url = f"{BASE_URL}/packages/download-manifest"
    payload = {"nodeIds": [node_id]}

    response = requests.post(
        manifest_url,
        json=payload,
        headers=auth_client.get_auth_headers()
    )
    response.raise_for_status()

    manifest = response.json()
    data = manifest.get("data", [])
    if not data:
        raise ValueError(f"No download URLs returned for node {node_id}")

    download_url = data[0].get("url")
    if not download_url:
        raise ValueError("Manifest response missing 'url' key")

    file_response = requests.get(download_url)
    file_response.raise_for_status()

    return file_response.text


def csv_to_json(csv_content: str) -> List[Dict[str, Any]]:
    """Convert CSV/TSV content to a list of JSON records."""
    # Auto-detect delimiter
    dialect = csv.Sniffer().sniff(csv_content[:1024], delimiters=',\t')
    reader = csv.DictReader(io.StringIO(csv_content), dialect=dialect)
    return list(reader)


def transform_record(record: Dict[str, Any], filename: Optional[str] = None, is_ieeg_sidecar: bool = False) -> Dict[str, Any]:
    """Apply transformations to a record (type conversions, etc.)."""

    # For ieeg sidecar records with the new schema
    if is_ieeg_sidecar:
        # Inject id from filename (without extension)
        if filename:
            # Remove extension to get id like "sub-PennEPI00212_ses-postimplant_task-clinical_ieeg"
            record_id = filename.rsplit('.', 1)[0] if '.' in filename else filename
            record["id"] = record_id

        # Keep SamplingFrequency as string (new schema expects string)
        if "SamplingFrequency" in record:
            record["SamplingFrequency"] = str(record["SamplingFrequency"])

        # Keep HardwareFilters values as strings (new schema expects strings)
        if "HardwareFilters" in record and isinstance(record["HardwareFilters"], dict):
            for filter_name, filter_values in record["HardwareFilters"].items():
                if isinstance(filter_values, dict):
                    for key in ["min (Hz)", "max (Hz)"]:
                        if key in filter_values:
                            filter_values[key] = str(filter_values[key])

        return record

    # --- Below is for NON-ieeg sidecar records (participants, dataset_description) ---

    # Convert age_intervention to number if present (handles "58.9" -> 58.9)
    # If it's "n/a" or can't be converted, remove it (schema only allows number)
    if "age_intervention" in record:
        try:
            record["age_intervention"] = float(record["age_intervention"])
        except (ValueError, TypeError):
            del record["age_intervention"]  # Remove if not a valid number

    # Fix typo: "home sapiens" -> "homo sapiens"
    if record.get("species") == "home sapiens":
        record["species"] = "homo sapiens"

    # Convert seizure_Engel scores to number or keep "n/a"
    for field in ["seizure_Engel12m", "seizure_Engel24m"]:
        if field in record:
            val = record[field]
            if val != "n/a":
                try:
                    record[field] = float(val)
                except (ValueError, TypeError):
                    del record[field]

    # Convert fiveSenseScore to number or keep "n/a"
    if "fiveSenseScore" in record:
        val = record["fiveSenseScore"]
        if val != "n/a":
            try:
                record["fiveSenseScore"] = float(val)
            except (ValueError, TypeError):
                del record["fiveSenseScore"]

    # Convert SamplingFrequency to number (old schema requires number, not string)
    if "SamplingFrequency" in record:
        try:
            record["SamplingFrequency"] = float(record["SamplingFrequency"])
        except (ValueError, TypeError):
            pass

    # Convert HardwareFilters nested values to numbers (old schema)
    # Schema: HardwareFilters.*.min (Hz) and max (Hz) should be numbers
    if "HardwareFilters" in record and isinstance(record["HardwareFilters"], dict):
        for filter_name, filter_values in record["HardwareFilters"].items():
            if isinstance(filter_values, dict):
                for key in ["min (Hz)", "max (Hz)"]:
                    if key in filter_values:
                        try:
                            filter_values[key] = float(filter_values[key])
                        except (ValueError, TypeError):
                            pass

    # Required fields that should never be removed
    required_fields = {"participant_id", "species", "population", "sex"}

    # Remove keys with empty string values (invalid for enum fields)
    # Keep required fields even if empty
    keys_to_remove = [
        key for key, value in record.items()
        if value == "" and key not in required_fields
    ]
    for key in keys_to_remove:
        del record[key]

    # Known schema fields for participants model - remove unknown fields
    # (additionalProperties: false means extra fields cause validation errors)
    participants_fields = {
        "participant_id", "species", "population", "sex",
        "MRI_lesion", "MRI_lesionType", "MRI_lesionDetails",
        "ieeg_isFocal", "age_intervention", "intervention_type",
        "intervention_side", "intervention_location",
        "seizure_Engel12m", "seizure_Engel24m", "fiveSenseScore"
    }

    # If this looks like a participants record, filter to known fields
    if "participant_id" in record:
        unknown_keys = [k for k in record.keys() if k not in participants_fields]
        for key in unknown_keys:
            del record[key]

    # Transform Authors field for dataset_description records
    # Schema expects array of Author objects {first_name, last_name}, not strings
    if "Authors" in record and isinstance(record["Authors"], list):
        transformed_authors = []
        for author in record["Authors"]:
            if isinstance(author, str):
                # Parse "FirstName LastName" or just use as last_name if no space
                parts = author.strip().split(None, 1)  # Split on first whitespace
                if len(parts) == 2:
                    transformed_authors.append({
                        "first_name": parts[0],
                        "last_name": parts[1]
                    })
                elif len(parts) == 1 and parts[0]:
                    # Single name - use as last_name
                    transformed_authors.append({
                        "first_name": "",
                        "last_name": parts[0]
                    })
                # Skip empty strings or "[Unspecified]" type placeholders
            elif isinstance(author, dict):
                # Already an object, keep it
                transformed_authors.append(author)
        record["Authors"] = transformed_authors if transformed_authors else []

    return record


def extract_data(file_content: str, filename: str, is_ieeg_sidecar: bool = False) -> List[Dict[str, Any]]:
    """
    Extract data from file content and convert to JSON format.

    Args:
        file_content: Raw file content as string
        filename: The filename (used to determine format and for id injection)
        is_ieeg_sidecar: If True, applies ieeg sidecar transformations (string types, id injection)

    Returns:
        List of records as dictionaries
    """
    # Determine format from filename
    if filename.endswith('.json'):
        data = json.loads(file_content)
        # Ensure it's a list of records
        if isinstance(data, dict):
            records = [data]
        else:
            records = data
    elif filename.endswith('.csv') or filename.endswith('.tsv'):
        records = csv_to_json(file_content)
    else:
        # Try CSV first, then JSON
        try:
            records = csv_to_json(file_content)
        except Exception:
            records = json.loads(file_content)

    # Apply transformations to each record
    return [transform_record(r, filename=filename, is_ieeg_sidecar=is_ieeg_sidecar) for r in records]


def post_records(
    auth_client: AuthenticationClient,
    model_id: str,
    records: List[Dict],
    dataset_id: str,
    dry_run: bool = False
) -> bool:
    """
    POST records to the model endpoint.

    POST https://api2.pennsieve.io/metadata/models/{MODEL_ID}/records?dataset_id={DATASET_ID}
    Body: {"records": [...]}
    """
    encoded_dataset_id = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models/{model_id}/records?dataset_id={encoded_dataset_id}"
    payload = {"records": records}

    print(f"    URL: {url}")
    print(f"    Payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        print(f"    [DRY-RUN] Would POST {len(records)} records")
        return True

    response = requests.post(url, json=payload, headers=auth_client.get_auth_headers())
    if not response.ok:
        print(f"    Response status: {response.status_code}")
        print(f"    Response body: {response.text}")
    response.raise_for_status()
    print(f"    Posted {len(records)} records successfully")
    return True


def process_dataset(
    auth_client: AuthenticationClient,
    dataset_name: str,
    all_datasets: List[Dict],
    file_pattern: str,
    template_id: Optional[str],
    template_version: int,
    model_name: Optional[str],
    display_name: Optional[str],
    description: str,
    existing_model_id: Optional[str] = None,
    force_reload: bool = False,
    dry_run: bool = False,
    is_ieeg_sidecar: bool = False
) -> bool:
    """
    Process a single dataset: create model, find file, extract data, post records.

    Args:
        is_ieeg_sidecar: If True, applies ieeg sidecar transformations (string types, id injection)

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Processing dataset: {dataset_name}")
    print(f"{'='*60}")

    # Find dataset
    dataset = find_dataset_by_name(dataset_name, all_datasets)
    if not dataset:
        print(f"  ERROR: Dataset not found: {dataset_name}")
        return False

    # Dataset ID is in content.id (format: N:dataset:uuid)
    content = dataset.get("content", {})
    dataset_id = content.get("id")

    if not dataset_id:
        print(f"  DEBUG: Dataset structure: {json.dumps(dataset, indent=2)[:500]}")
        print(f"  ERROR: Could not find dataset ID")
        return False

    print(f"  Dataset ID: {dataset_id}")

    # Step 1: Create model from template OR use existing model
    if existing_model_id:
        print(f"\n  Step 1: Using existing model...")
        print(f"    Model ID: {existing_model_id}")
        model_id = existing_model_id
    else:
        print(f"\n  Step 1: Creating model from template...")
        print(f"    Template ID: {template_id} (v{template_version})")
        print(f"    Model name: {model_name}")
        try:
            model_id = create_model_from_template(
                auth_client,
                template_id,
                dataset_id,
                model_name=model_name,
                display_name=display_name,
                description=description,
                template_version=template_version,
                dry_run=dry_run
            )
        except requests.HTTPError as e:
            print(f"  ERROR: Failed to create model from template: {e}")
            return False

    # Step 2: Get packages and find target file
    print(f"\n  Step 2: Finding target file (pattern: {file_pattern})...")
    packages = load_data(f"packages_{dataset_name}", force_reload=force_reload)
    if packages is None:
        print(f"    Fetching packages from network...")
        packages = get_dataset_packages(auth_client, dataset_id)
        save_data(packages, f"packages_{dataset_name}")
    else:
        print(f"    Using cached packages ({len(packages)} packages)")

    target_pkg = find_target_file(packages, file_pattern, debug=True)
    if not target_pkg:
        print(f"  ERROR: No file matching pattern '{file_pattern}' found")
        return False

    target_name = target_pkg.get("content", {}).get("name")
    target_node_id = target_pkg.get("content", {}).get("nodeId")
    print(f"    Found: {target_name} (nodeId: {target_node_id})")

    # Step 3: Download and extract data
    print(f"\n  Step 3: Downloading and extracting data...")
    if not dry_run:
        try:
            file_content = download_file_content(auth_client, target_node_id)
            records = extract_data(file_content, target_name, is_ieeg_sidecar=is_ieeg_sidecar)
            print(f"    Extracted {len(records)} records")
        except Exception as e:
            print(f"  ERROR: Failed to download/extract data: {e}")
            return False
    else:
        print(f"    [DRY-RUN] Would download and extract data from {target_name}")
        records = []

    # Step 4: Post records to model
    print(f"\n  Step 4: Posting records to model...")
    if not dry_run:
        try:
            success = post_records(
                auth_client,
                model_id,
                records,
                dataset_id,
                dry_run=dry_run
            )
            if success:
                print(f"  SUCCESS: Completed processing for {dataset_name}")
            else:
                print(f"  ERROR: Failed to post records")
                return False
        except requests.HTTPError as e:
            print(f"  ERROR: Failed to post records: {e}")
            return False
    else:
        print(f"    [DRY-RUN] Would post records to model {model_id}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Create models from template and populate with Pennsieve file data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find files ending in _ieeg.json and create model from template
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00086 --file-pattern _ieeg.json \\
      --template-id d6292e13-... \\
      --model-name bids_ieeg_sidecar --display-name "BIDS iEEG sidecar"

  # Process all datasets
  %(prog)s --api-key KEY --api-secret SECRET --all \\
      --file-pattern participants.tsv \\
      --template-id abc123-... \\
      --model-name participants --display-name "Participants"

  # Dry run to preview changes
  %(prog)s --api-key KEY --api-secret SECRET --all \\
      --file-pattern _ieeg.json \\
      --template-id d6292e13-... \\
      --model-name bids_ieeg_sidecar --display-name "BIDS iEEG sidecar" \\
      --dry-run
        """
    )

    parser.add_argument(
        '--api-key',
        required=True,
        help='Pennsieve API key'
    )

    parser.add_argument(
        '--api-secret',
        required=True,
        help='Pennsieve API secret'
    )

    # Dataset selection (mutually exclusive)
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        '--datasets',
        nargs='+',
        help='Dataset names to process (e.g., PennEPI00086 PennEPI00087)'
    )
    dataset_group.add_argument(
        '--all',
        action='store_true',
        help='Process all datasets in Pennsieve'
    )

    # File and model configuration
    parser.add_argument(
        '--file-pattern',
        help='File pattern to search for (e.g., _ieeg.json, participants.tsv). Required unless --config is provided.'
    )

    parser.add_argument(
        '--template-id',
        help='Template ID to create the model from (required unless --model-id is provided)'
    )

    parser.add_argument(
        '--template-version',
        type=int,
        default=1,
        help='Template version (default: 1)'
    )

    parser.add_argument(
        '--model-name',
        help='Internal name for the model (e.g., bids_ieeg_sidecar) - required for model creation'
    )

    parser.add_argument(
        '--display-name',
        help='Display name for the model (e.g., "BIDS iEEG sidecar") - required for model creation'
    )

    parser.add_argument(
        '--description',
        default='',
        help='Description for the model'
    )

    parser.add_argument(
        '--model-id',
        help='Use existing model ID instead of creating from template (skips model creation)'
    )

    parser.add_argument(
        '--config',
        help='Path to JSON config file with multiple model definitions'
    )

    # Options
    parser.add_argument(
        '--force-reload',
        action='store_true',
        help='Force reload data from network, bypassing cache'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    parser.add_argument(
        '--ieeg-sidecar',
        action='store_true',
        help='Enable ieeg sidecar mode: injects filename as "id" field and keeps SamplingFrequency/HardwareFilters as strings'
    )

    args = parser.parse_args()

    # Validate: need --config OR --model-id OR (--template-id + --model-name + --display-name + --file-pattern)
    if not args.config:
        if not args.file_pattern:
            parser.error("--file-pattern is required unless --config is provided")
        if not args.model_id:
            if not args.template_id:
                parser.error("--template-id is required unless --model-id or --config is provided")
            if not args.model_name:
                parser.error("--model-name is required unless --model-id or --config is provided")
            if not args.display_name:
                parser.error("--display-name is required unless --model-id or --config is provided")

    # Load config file if provided
    model_configs = []
    if args.config:
        with open(args.config, 'r') as f:
            config_data = json.load(f)
        model_configs = config_data.get("models", [])
        if not model_configs:
            parser.error(f"No models defined in config file: {args.config}")
        print(f"Loaded {len(model_configs)} model configurations from {args.config}")
    else:
        # Single model from command line args
        model_configs = [{
            "template_id": args.template_id,
            "template_version": args.template_version,
            "model_name": args.model_name,
            "display_name": args.display_name,
            "description": args.description,
            "file_pattern": args.file_pattern,
            "model_id": args.model_id,  # For existing model
        }]

    if args.dry_run:
        print("\n" + "="*60)
        print("DRY RUN MODE - No actual changes will be made")
        print("="*60)

    # Authenticate
    print("\nAuthenticating with Pennsieve...")
    auth_client = AuthenticationClient()
    try:
        auth_client.authenticate(args.api_key, args.api_secret)
        print("Authentication successful")
    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        sys.exit(1)

    # Get all datasets
    print("\nFetching datasets...")
    all_datasets = load_data("all_datasets", force_reload=args.force_reload)
    if all_datasets is None:
        all_datasets = get_all_datasets(auth_client)
        save_data(all_datasets, "all_datasets")
    print(f"Found {len(all_datasets)} datasets")

    # Determine which datasets to process
    if args.all:
        dataset_names = [
            ds.get("content", {}).get("name", "").strip()
            for ds in all_datasets
            if ds.get("content", {}).get("name")
        ]
    else:
        dataset_names = args.datasets

    print(f"\nConfiguration:")
    print(f"  Datasets to process: {len(dataset_names)}")
    print(f"  Models to process: {len(model_configs)}")
    if len(model_configs) == 1:
        cfg = model_configs[0]
        print(f"  File pattern: {cfg.get('file_pattern')}")
        if cfg.get("model_id"):
            print(f"  Using existing model ID: {cfg.get('model_id')}")
        else:
            print(f"  Template ID: {cfg.get('template_id')} (v{cfg.get('template_version', 1)})")
            print(f"  Model name: {cfg.get('model_name')}")
            print(f"  Display name: {cfg.get('display_name')}")
    else:
        for i, cfg in enumerate(model_configs, 1):
            print(f"  [{i}] {cfg.get('display_name', cfg.get('model_name'))} -> {cfg.get('file_pattern')}")

    # Process each dataset and each model config
    success_count = 0
    fail_count = 0
    total_operations = len(dataset_names) * len(model_configs)

    for dataset_name in dataset_names:
        for model_cfg in model_configs:
            try:
                success = process_dataset(
                    auth_client,
                    dataset_name,
                    all_datasets,
                    file_pattern=model_cfg.get("file_pattern"),
                    template_id=model_cfg.get("template_id"),
                    template_version=model_cfg.get("template_version", 1),
                    model_name=model_cfg.get("model_name"),
                    display_name=model_cfg.get("display_name"),
                    description=model_cfg.get("description", ""),
                    existing_model_id=model_cfg.get("model_id"),
                    force_reload=args.force_reload,
                    dry_run=args.dry_run,
                    is_ieeg_sidecar=args.ieeg_sidecar
                )
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"  ERROR: Exception processing {dataset_name} / {model_cfg.get('model_name')}: {e}")
                fail_count += 1

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total datasets: {len(dataset_names)}")
    print(f"Total models: {len(model_configs)}")
    print(f"Total operations: {total_operations}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")

    if args.dry_run:
        print("\n(Dry-run mode: no actual changes were made)")


if __name__ == '__main__':
    main()
