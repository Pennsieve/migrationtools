#!/usr/bin/env python3
"""
Create Models Script

Creates models from templates across Pennsieve datasets matching the PennEPI pattern.

Usage:
  # Dry run — all PennEPI datasets, all 5 models
  python create_models.py --api-key KEY --api-secret SECRET --dry-run

  # Specific datasets with exclusions
  python create_models.py --api-key KEY --api-secret SECRET \
      --datasets PennEPI00049 PennEPI00111 --exclude PennEPI00214 --dry-run

  # Execute for real — all PennEPI datasets
  python create_models.py --api-key KEY --api-secret SECRET --execute

  # Only create specific models
  python create_models.py --api-key KEY --api-secret SECRET \
      --datasets PennEPI00049 --models person mri --execute
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from model_populator import (
    AuthenticationClient,
    get_all_datasets,
    create_model_from_template,
)

SCRIPT_DIR = Path(__file__).parent
DEFAULT_MAPPINGS_FILE = SCRIPT_DIR / "schemas" / "omop_mappings_v2.json"

# Datasets that are always excluded (already done manually)
DEFAULT_EXCLUDES = {"PennEPI00124"}

PREFIX = "PennEPI"


def load_model_templates(mappings_file: Path) -> Dict[str, Dict]:
    """
    Load model templates from the mappings JSON file (the golden source).

    Returns a dict keyed by model short name with template_id, model_name,
    and display_name.
    """
    with open(mappings_file) as f:
        mappings = json.load(f)

    templates = {}
    for key, config in mappings.get("models", {}).items():
        templates[key] = {
            "template_id": config["template_id"],
            "model_name": config.get("model_name", key),
            "display_name": config.get("display_name", config.get("model_name", key).replace("_", " ").title()),
        }
    return templates


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def filter_datasets(
    all_datasets: List[Dict],
    dataset_names: Optional[List[str]],
    exclude: Optional[List[str]],
) -> List[Dict]:
    """
    Filter datasets to process.

    If dataset_names is provided, only those datasets are included.
    Otherwise, all datasets matching the PennEPI prefix are included.
    Exclusions are always applied on top.
    """
    excludes = set(DEFAULT_EXCLUDES)
    if exclude:
        excludes.update(exclude)

    filtered = []
    for ds in all_datasets:
        name = ds.get("content", {}).get("name", "")

        if dataset_names:
            if name not in dataset_names:
                continue
        else:
            if not name.startswith(PREFIX):
                continue

        if name in excludes:
            continue

        filtered.append(ds)

    return filtered


def process_datasets(
    auth_client: AuthenticationClient,
    datasets: List[Dict],
    model_keys: List[str],
    model_templates: Dict[str, Dict],
    dry_run: bool,
    verbose: bool,
) -> Tuple[int, int, int]:
    """
    Create models for each dataset.

    Returns:
        (models_created, models_skipped, models_failed)
    """
    created = 0
    skipped = 0
    failed = 0

    for ds in datasets:
        ds_name = ds.get("content", {}).get("name", "Unknown")
        ds_id = ds.get("content", {}).get("id")

        if not ds_id:
            print(f"  SKIP: {ds_name} — no dataset ID")
            skipped += 1
            continue

        print(f"\n{'='*60}")
        print(f"Dataset: {ds_name}  (ID: {ds_id})")
        print(f"{'='*60}")

        for key in model_keys:
            tmpl = model_templates[key]

            print(f"\n  Model: {tmpl['display_name']}")

            try:
                model_id = create_model_from_template(
                    auth_client,
                    template_id=tmpl["template_id"],
                    dataset_id=ds_id,
                    model_name=tmpl["model_name"],
                    display_name=tmpl["display_name"],
                    dry_run=dry_run,
                )

                if model_id:
                    created += 1
                else:
                    print(f"    WARNING: No model ID returned")
                    failed += 1

            except Exception as e:
                print(f"    ERROR: {e}")
                failed += 1

    return created, skipped, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create models from templates across PennEPI datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run — all PennEPI datasets, all models
  python create_models.py --api-key KEY --api-secret SECRET --dry-run

  # Specific datasets, exclude one
  python create_models.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00049 PennEPI00111 --exclude PennEPI00214 --dry-run

  # Execute for real
  python create_models.py --api-key KEY --api-secret SECRET --execute

  # Only create specific models
  python create_models.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00049 --models person mri --execute

  # Use a different mappings file
  python create_models.py --api-key KEY --api-secret SECRET \\
      --mappings schemas/omop_mappings_v2.json --dry-run
        """,
    )

    parser.add_argument("--api-key", required=True, help="Pennsieve API key")
    parser.add_argument("--api-secret", required=True, help="Pennsieve API secret")
    parser.add_argument("--mappings", metavar="FILE",
                        help=f"Path to mappings JSON file (default: {DEFAULT_MAPPINGS_FILE})")

    parser.add_argument(
        "--datasets", nargs="+", metavar="NAME",
        help="Explicit list of dataset names (default: all PennEPI datasets)",
    )
    parser.add_argument(
        "--exclude", nargs="+", metavar="NAME",
        help="Datasets to skip (PennEPI00124 is always excluded)",
    )
    parser.add_argument(
        "--models", nargs="+", metavar="MODEL",
        help="Which models to create (default: all)",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    mode.add_argument("--execute", action="store_true", help="Actually create the models")

    parser.add_argument("--force-reload", action="store_true", help="Bypass dataset cache")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load templates from mappings file
    mappings_file = Path(args.mappings) if args.mappings else DEFAULT_MAPPINGS_FILE
    model_templates = load_model_templates(mappings_file)
    print(f"Loaded {len(model_templates)} model templates from {mappings_file}")

    # Validate --models choices against what's in the mappings file
    if args.models:
        for m in args.models:
            if m not in model_templates:
                parser.error(f"Unknown model '{m}'. Available: {', '.join(model_templates.keys())}")

    model_keys = args.models or list(model_templates.keys())

    # --- Authenticate ---
    print("Authenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful\n")

    # --- Fetch datasets ---
    print("Fetching datasets...")
    all_datasets = get_all_datasets(auth_client)
    print(f"Total datasets available: {len(all_datasets)}")

    datasets = filter_datasets(all_datasets, args.datasets, args.exclude)

    if not datasets:
        print("No datasets matched the criteria.")
        sys.exit(2)

    print(f"Datasets to process: {len(datasets)}")
    print(f"Models per dataset:  {len(model_keys)} ({', '.join(model_keys)})")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No actual changes will be made")

    # --- Process ---
    created, skipped, failed = process_datasets(
        auth_client, datasets, model_keys, model_templates,
        dry_run=args.dry_run, verbose=args.verbose,
    )

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Datasets processed: {len(datasets)}")
    print(f"Models created:     {created}")
    print(f"Models skipped:     {skipped}")
    print(f"Models failed:      {failed}")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No actual changes were made")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
