#!/usr/bin/env python3
"""
Create Relationships Script

Creates relationships between model records across Pennsieve datasets.
Uses the bulk relationship endpoint to link records by their key properties
(x-pennsieve-key fields like person_id and session_id).

Usage:
  # Dry run for a specific dataset
  python create_relationships.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00214 --dry-run

  # Execute for real on multiple datasets
  python create_relationships.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00214 PennEPI00215

  # All PennEPI datasets
  python create_relationships.py --api-key KEY --api-secret SECRET \\
      --prefix PennEPI

  # Verbose output
  python create_relationships.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00214 --verbose
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

import requests

from helpers import load_data, save_data, BASE_URL
from model_populator import (
    AuthenticationClient,
    get_all_datasets,
    find_dataset_by_name,
    get_dataset_packages,
    download_file_content,
)

API2_BASE_URL = "https://api2.pennsieve.io"
SCRIPT_DIR = Path(__file__).parent
DEFAULT_MAPPINGS_FILE = SCRIPT_DIR / "schemas" / "omop_mappings_v2.json"


def load_mappings(mappings_file: Path) -> Dict:
    """Load model and relationship config from mappings file."""
    with open(mappings_file) as f:
        return json.load(f)


def get_all_model_ids(
    auth_client: AuthenticationClient,
    dataset_id: str,
) -> Dict[str, str]:
    """
    Get all models for a dataset.

    GET https://api2.pennsieve.io/metadata/models?dataset_id={DATASET_ID}

    Returns:
        Dict mapping model name -> model ID
    """
    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded}"
    response = requests.get(url, headers=auth_client.get_auth_headers())
    response.raise_for_status()

    models = {}
    for item in response.json():
        model = item.get("model", {})
        name = model.get("name")
        mid = model.get("id")
        if name and mid:
            models[name] = mid
    return models


def get_participant_id(
    auth_client: AuthenticationClient,
    packages: List[Dict],
) -> Optional[str]:
    """Extract participant_id from participants.tsv in the dataset."""
    for pkg in packages:
        content = pkg.get("content", {})
        name = content.get("name", "")
        if name == "participants.tsv" and not name.startswith("__DELETED__"):
            node_id = content.get("nodeId")
            text = download_file_content(auth_client, node_id)
            dialect = csv.Sniffer().sniff(text[:1024], delimiters=",\t")
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            for row in reader:
                return row.get("participant_id")
    return None


def build_key_record(
    model_key: str,
    person_id: str,
    mappings: Dict,
) -> Dict[str, str]:
    """
    Build a record containing only key property values for a model.

    Uses key_fields from the mappings config and resolves values
    from static_value definitions in the field config.
    """
    model_config = mappings["models"].get(model_key, {})
    key_fields = model_config.get("key_fields", ["person_id"])
    fields_config = model_config.get("fields", {})

    record = {}
    for field in key_fields:
        if field == "person_id":
            record["person_id"] = person_id
        else:
            # Look up the value from the field config (typically static_value)
            field_config = fields_config.get(field, {})
            if "static_value" in field_config:
                record[field] = field_config["static_value"]

    return record


def create_relationship(
    auth_client: AuthenticationClient,
    dataset_id: str,
    source_model_id: str,
    target_model_id: str,
    source_record: Dict,
    target_record: Dict,
    relationship_type: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Create a relationship between two records using the bulk endpoint.

    POST https://api2.pennsieve.io/metadata/relationships?dataset_id={DATASET_ID}

    Payload:
        {
            "source_model_id": "...",
            "target_model_id": "...",
            "record_relationships": [
                {
                    "source_record": { key properties },
                    "target_record": { key properties },
                    "relationship_type": "BELONGS_TO"
                }
            ]
        }
    """
    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/relationships?dataset_id={encoded}"

    payload = {
        "source_model_id": source_model_id,
        "target_model_id": target_model_id,
        "record_relationships": [
            {
                "source_record": source_record,
                "target_record": target_record,
                "relationship_type": relationship_type,
            }
        ],
    }

    if verbose:
        print(f"      URL: {url}")
        print(f"      Payload: {json.dumps(payload, indent=2)}")

    if dry_run:
        print(f"      [DRY-RUN] Would POST relationship")
        return True

    response = requests.post(
        url, json=payload, headers=auth_client.get_auth_headers()
    )

    if response.ok:
        print(f"      Created successfully")
        return True
    else:
        print(f"      ERROR: {response.status_code} - {response.text}")
        return False


def process_dataset(
    auth_client: AuthenticationClient,
    dataset_name: str,
    all_datasets: List[Dict],
    mappings: Dict,
    force_reload: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> Tuple[int, int]:
    """
    Create all configured relationships for a single dataset.

    Returns:
        Tuple of (success_count, failure_count)
    """
    print(f"\n{'='*60}")
    print(f"Processing dataset: {dataset_name}")
    print(f"{'='*60}")

    # Find dataset
    dataset = find_dataset_by_name(dataset_name, all_datasets)
    if not dataset:
        print(f"  ERROR: Dataset not found: {dataset_name}")
        return (0, 0)

    dataset_id = dataset.get("content", {}).get("id")
    if not dataset_id:
        print(f"  ERROR: Could not get dataset ID")
        return (0, 0)

    print(f"  Dataset ID: {dataset_id}")

    # Get all model IDs in this dataset
    model_ids = get_all_model_ids(auth_client, dataset_id)
    print(f"  Models found: {', '.join(model_ids.keys())}")

    # Get participant_id
    cache_key = f"packages_{dataset_name}"
    packages = load_data(cache_key, force_reload=force_reload)
    if packages is None:
        print(f"  Fetching packages...")
        packages = get_dataset_packages(auth_client, dataset_id)
        save_data(packages, cache_key)

    person_id = get_participant_id(auth_client, packages)
    if not person_id:
        print(f"  SKIP: No participant_id found in participants.tsv")
        return (0, 0)

    print(f"  Participant ID: {person_id}")

    # Process each configured relationship
    relationships = mappings.get("relationships", [])
    if not relationships:
        print(f"  WARNING: No relationships configured in mappings")
        return (0, 0)

    success_count = 0
    failure_count = 0

    for rel in relationships:
        source_key = rel["source"]
        target_key = rel["target"]
        rel_type = rel["type"]

        source_model_name = mappings["models"][source_key]["model_name"]
        target_model_name = mappings["models"][target_key]["model_name"]

        source_model_id = model_ids.get(source_model_name)
        target_model_id = model_ids.get(target_model_name)

        print(f"\n  {source_model_name} --[{rel_type}]--> {target_model_name}")

        if not source_model_id:
            print(f"    SKIP: Source model '{source_model_name}' not found")
            continue
        if not target_model_id:
            print(f"    SKIP: Target model '{target_model_name}' not found")
            continue

        source_record = build_key_record(source_key, person_id, mappings)
        target_record = build_key_record(target_key, person_id, mappings)

        if verbose:
            print(f"    Source record: {json.dumps(source_record)}")
            print(f"    Target record: {json.dumps(target_record)}")

        ok = create_relationship(
            auth_client,
            dataset_id,
            source_model_id,
            target_model_id,
            source_record,
            target_record,
            rel_type,
            dry_run=dry_run,
            verbose=verbose,
        )

        if ok:
            success_count += 1
        else:
            failure_count += 1

    return (success_count, failure_count)


def main():
    parser = argparse.ArgumentParser(
        description="Create relationships between model records across Pennsieve datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run for a specific dataset
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00214 --dry-run

  # Execute for real
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00214 PennEPI00215

  # All PennEPI datasets
  %(prog)s --api-key KEY --api-secret SECRET \\
      --prefix PennEPI
        """,
    )

    parser.add_argument("--api-key", required=True, help="Pennsieve API key")
    parser.add_argument("--api-secret", required=True, help="Pennsieve API secret")

    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        "--datasets", nargs="+", metavar="NAME", help="Dataset names to process"
    )
    dataset_group.add_argument(
        "--prefix", metavar="PREFIX", help="Process datasets starting with this prefix"
    )

    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--force-reload", action="store_true", help="Bypass cache")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--mappings", metavar="FILE", help="Path to mappings JSON file")

    args = parser.parse_args()

    # Load mappings
    mappings_file = Path(args.mappings) if args.mappings else DEFAULT_MAPPINGS_FILE
    mappings = load_mappings(mappings_file)

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No actual changes will be made")
        print("=" * 60)

    # Authenticate
    print("\nAuthenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")

    # Get all datasets
    print("\nFetching datasets...")
    all_datasets = load_data("all_datasets", force_reload=args.force_reload)
    if all_datasets is None:
        all_datasets = get_all_datasets(auth_client)
        save_data(all_datasets, "all_datasets")
    print(f"Total datasets available: {len(all_datasets)}")

    # Filter datasets
    if args.datasets:
        dataset_names = args.datasets
    else:
        dataset_names = [
            ds.get("content", {}).get("name", "")
            for ds in all_datasets
            if ds.get("content", {}).get("name", "").startswith(args.prefix)
        ]

    if not dataset_names:
        print("No datasets matched the criteria.")
        sys.exit(2)

    print(f"Datasets to process: {len(dataset_names)}")

    relationships = mappings.get("relationships", [])
    print(f"Relationships to create per dataset: {len(relationships)}")
    for rel in relationships:
        print(f"  {rel['source']} --[{rel['type']}]--> {rel['target']}")

    # Process
    total_success = 0
    total_failures = 0

    for ds_name in dataset_names:
        success, failures = process_dataset(
            auth_client,
            ds_name,
            all_datasets,
            mappings,
            force_reload=args.force_reload,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        total_success += success
        total_failures += failures

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Datasets processed: {len(dataset_names)}")
    print(f"Relationships created: {total_success}")
    print(f"Relationships failed: {total_failures}")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No actual changes were made")

    if total_failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
