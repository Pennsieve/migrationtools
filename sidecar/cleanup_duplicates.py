#!/usr/bin/env python3
"""
Pennsieve Duplicate File Cleanup Script

When files are re-uploaded to Pennsieve, duplicates get a (1) suffix.
This script finds and cleans up these duplicates by:
1. Finding the original file and its (1) duplicate
2. Deleting the original
3. Renaming the (1) version to remove the suffix

Only acts when BOTH files exist in the same folder.
"""

import argparse
import re
import sys
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

from helpers import (
    get_all_datasets,
    get_dataset_packages,
    load_data,
    save_data,
    API_KEY,
    BASE_URL,
)

HEADERS = {"accept": "*/*", "content-type": "application/json"}


def find_dataset_by_name(dataset_name: str) -> Optional[Dict]:
    """Find a dataset by name and return its info."""
    datasets = get_all_datasets()
    for ds in datasets:
        content = ds.get("content", {})
        if content.get("name", "").strip() == dataset_name:
            return ds
    return None


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


def parse_file_path(file_path: str) -> Tuple[str, str]:
    """
    Parse a file path into (parent_folder, filename).

    Examples:
        'ieeg/file.json' -> ('ieeg', 'file.json')
        'ieeg/sub/file.json' -> ('ieeg/sub', 'file.json')
        'file.json' -> ('', 'file.json')
    """
    p = Path(file_path)
    parent = str(p.parent) if p.parent != Path('.') else ''
    return (parent, p.name)


def get_duplicate_name(filename: str) -> str:
    """
    Generate the (1) duplicate name for a file.

    Examples:
        'file.json' -> 'file (1).json'
        'file.tar.gz' -> 'file (1).tar.gz'  # Only last extension
    """
    p = Path(filename)
    stem = p.stem
    suffix = p.suffix
    return f"{stem} (1){suffix}"


def get_original_name(duplicate_name: str) -> str:
    """
    Get the original name from a (1) duplicate name.

    Examples:
        'file (1).json' -> 'file.json'
    """
    # Match pattern like "name (1).ext"
    match = re.match(r'^(.+) \(1\)(\.[^.]+)$', duplicate_name)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return duplicate_name


def delete_package(package_id: str, dry_run: bool = True) -> bool:
    """Delete a package by ID."""
    if dry_run:
        print(f"  [DRY-RUN] Would delete package: {package_id}")
        return True

    if not API_KEY:
        print("  ERROR: PENNSIEVE_API_KEY not set.")
        return False

    url = f"{BASE_URL}/data/delete?api_key={API_KEY}"
    payload = {"things": [package_id]}

    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"  Deleted package: {package_id}")
        return True
    except requests.RequestException as e:
        print(f"  ERROR: Failed to delete package {package_id}: {e}")
        return False


def rename_package(package_id: str, new_name: str, dry_run: bool = True) -> bool:
    """Rename a package by ID."""
    if dry_run:
        print(f"  [DRY-RUN] Would rename package {package_id} -> '{new_name}'")
        return True

    if not API_KEY:
        print("  ERROR: PENNSIEVE_API_KEY not set.")
        return False

    url = f"{BASE_URL}/packages/{package_id}?updateStorage=false&api_key={API_KEY}"
    payload = {"name": new_name}

    try:
        response = requests.put(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"  Renamed package -> '{new_name}'")
        return True
    except requests.RequestException as e:
        print(f"  ERROR: Failed to rename package {package_id}: {e}")
        return False


def process_dataset(dataset_name: str, file_paths: List[str], dry_run: bool = True, force_reload: bool = False) -> Tuple[int, int]:
    """
    Process a single dataset, cleaning up duplicates for specified file paths.

    Returns:
        Tuple of (success_count, skip_count)
    """
    print(f"\n{'='*60}")
    print(f"Processing dataset: {dataset_name}")
    print(f"{'='*60}")

    # Find dataset
    dataset = find_dataset_by_name(dataset_name)
    if not dataset:
        print(f"  Dataset not found: {dataset_name}")
        return (0, len(file_paths))

    dataset_id = dataset.get("content", {}).get("id")
    print(f"  Dataset ID: {dataset_id}")

    # Get all packages (use cache if available)
    packages = load_data(f"package_{dataset_name}", force_reload=force_reload)
    if packages is None:
        print(f"  Fetching packages from network...")
        packages = get_dataset_packages(dataset_id)
        save_data(packages, f"package_{dataset_name}")
    else:
        print(f"  Using cached packages")
    print(f"  Found {len(packages)} packages")

    # Build lookup by (path, name)
    pkg_by_location: Dict[Tuple[str, str], Dict] = {}
    for pkg in packages:
        content = pkg.get("content", {})
        name = content.get("name", "")
        pkg_path = get_package_path(pkg, packages)
        pkg_by_location[(pkg_path, name)] = pkg
        # Debug: show sessions files
        if "sessions" in name.lower():
            print(f"    DEBUG: Found sessions file: path='{pkg_path}', name='{name}'")

    success_count = 0
    skip_count = 0

    for file_path_template in file_paths:
        # Replace {dataset} placeholder with actual dataset name
        file_path = file_path_template.replace("{dataset}", dataset_name)

        parent_folder, filename = parse_file_path(file_path)
        duplicate_name = get_duplicate_name(filename)

        print(f"\n  Looking for: {file_path}")
        print(f"    Original: {parent_folder}/{filename}" if parent_folder else f"    Original: {filename}")
        print(f"    Duplicate: {parent_folder}/{duplicate_name}" if parent_folder else f"    Duplicate: {duplicate_name}")

        # Find both packages
        original_pkg = pkg_by_location.get((parent_folder, filename))
        duplicate_pkg = pkg_by_location.get((parent_folder, duplicate_name))

        if not original_pkg and not duplicate_pkg:
            print(f"    SKIP: Neither file found")
            skip_count += 1
            continue

        if original_pkg and not duplicate_pkg:
            print(f"    SKIP: Only original exists (no duplicate to replace with)")
            skip_count += 1
            continue

        if duplicate_pkg and not original_pkg:
            print(f"    SKIP: Only duplicate exists (no original to delete)")
            skip_count += 1
            continue

        # Both exist - proceed with cleanup
        original_id = original_pkg.get("content", {}).get("nodeId")
        duplicate_id = duplicate_pkg.get("content", {}).get("nodeId")

        print(f"    FOUND BOTH:")
        print(f"      Original ID: {original_id}")
        print(f"      Duplicate ID: {duplicate_id}")

        # Step 1: Delete original
        print(f"    Step 1: Delete original")
        if not delete_package(original_id, dry_run):
            print(f"    ERROR: Failed to delete original, skipping rename")
            skip_count += 1
            continue

        # Step 2: Rename duplicate to original name
        print(f"    Step 2: Rename duplicate")
        if not rename_package(duplicate_id, filename, dry_run):
            print(f"    ERROR: Failed to rename duplicate")
            skip_count += 1
            continue

        print(f"    SUCCESS: Cleaned up {filename}")
        success_count += 1

    return (success_count, skip_count)


def main():
    parser = argparse.ArgumentParser(
        description='Clean up duplicate files on Pennsieve (files with (1) suffix)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run for a single dataset and file
  %(prog)s --datasets PennEPI00086 --files ieeg/sub-PennEPI00086_coordsystem.json --dry-run

  # Use {dataset} placeholder for files that vary by dataset name
  %(prog)s --datasets PennEPI00082 PennEPI00083 --files "sub-{dataset}/sub-{dataset}_sessions.tsv" participants.tsv --dry-run
  # This expands to:
  #   - sub-PennEPI00082/sub-PennEPI00082_sessions.tsv for PennEPI00082
  #   - sub-PennEPI00083/sub-PennEPI00083_sessions.tsv for PennEPI00083

  # Actually perform the cleanup (no --dry-run)
  %(prog)s --datasets PennEPI00086 --files participants.tsv
        """
    )

    parser.add_argument(
        '--datasets',
        nargs='+',
        required=True,
        help='Dataset names to process (e.g., PennEPI00086 PennEPI00087)'
    )

    parser.add_argument(
        '--files',
        nargs='+',
        required=True,
        help='File paths to clean up, relative to dataset root. Use {dataset} as placeholder for dataset name (e.g., "sub-{dataset}/sub-{dataset}_sessions.tsv")'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes (recommended first)'
    )

    parser.add_argument(
        '--force-reload',
        action='store_true',
        help='Force reload packages from network, bypassing cache'
    )

    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: PENNSIEVE_API_KEY environment variable not set")
        sys.exit(1)

    if args.dry_run:
        print("\n" + "="*60)
        print("DRY RUN MODE - No actual changes will be made")
        print("="*60)

    print(f"\nDatasets to process: {args.datasets}")
    print(f"Files to clean up: {args.files}")

    total_success = 0
    total_skip = 0

    for dataset_name in args.datasets:
        success, skip = process_dataset(dataset_name, args.files, dry_run=args.dry_run, force_reload=args.force_reload)
        total_success += success
        total_skip += skip

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total datasets processed: {len(args.datasets)}")
    print(f"Files cleaned up: {total_success}")
    print(f"Files skipped: {total_skip}")

    if args.dry_run:
        print("\n(Dry-run mode: no actual changes were made)")


if __name__ == '__main__':
    main()
