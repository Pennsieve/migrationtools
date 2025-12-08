#!/usr/bin/env python3
"""
Delete Packages Script

Delete files/packages matching a pattern across Pennsieve datasets.

Safety features:
- Dry-run mode is the DEFAULT (must use --execute to actually delete)
- Lists all datasets and files that will be affected before any action
- Requires either --datasets or --pattern to specify which datasets to process

Examples:
    # Dry run: see what *_ieeg.json files would be deleted in specific datasets
    python delete_packages.py --datasets PennEPI00089 PennEPI00090 --file-pattern "*_ieeg.json"

    # Dry run: see what would be deleted across all datasets starting with "PennEPI"
    python delete_packages.py --prefix "PennEPI" --file-pattern "*_ieeg.json"

    # Actually delete (requires --execute flag)
    python delete_packages.py --datasets PennEPI00089 --file-pattern "*_ieeg.json" --execute

    # Force reload packages from network (bypass cache)
    python delete_packages.py --datasets PennEPI00089 --file-pattern "*.tsv" --force-reload
"""

import argparse
import os
import sys

from manage_datasets import PennsieveDatasetManager, logger


def main():
    parser = argparse.ArgumentParser(
        description='Delete packages matching a pattern across Pennsieve datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default): list files that would be deleted
  %(prog)s --datasets PennEPI00089 PennEPI00090 --file-pattern "*_ieeg.json"

  # Using prefix to match all datasets starting with "PennEPI"
  %(prog)s --prefix PennEPI --file-pattern "*_ieeg.json"

  # Actually perform deletion (requires --execute)
  %(prog)s --datasets PennEPI00089 --file-pattern "*_ieeg.json" --execute

  # Match all .tsv files
  %(prog)s --datasets PennEPI00089 --file-pattern "*.tsv"

  # Match specific sidecar files across all PennEPI datasets
  %(prog)s --prefix PennEPI --file-pattern "*_coordsystem.json"
        """
    )

    # Dataset selection (mutually exclusive group, one required)
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        '--datasets',
        nargs='+',
        metavar='DATASET',
        help='Explicit list of dataset names to process (e.g., PennEPI00089 PennEPI00090)'
    )
    dataset_group.add_argument(
        '--prefix',
        metavar='PREFIX',
        help='Match datasets whose names start with this prefix (e.g., "PennEPI")'
    )

    # File pattern(s) (required)
    parser.add_argument(
        '--file-pattern',
        nargs='+',
        required=True,
        metavar='GLOB',
        help='Glob pattern(s) for files to delete (e.g., "*_ieeg.json" "*_clinical.csv")'
    )

    # Safety and execution flags
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform deletions (default is dry-run mode)'
    )

    parser.add_argument(
        '--force-reload',
        action='store_true',
        help='Force reload packages from network, bypassing cache'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose/debug logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        import logging
        logger.setLevel(logging.DEBUG)

    # Get API key
    PENNSIEVE_API_KEY = "eyJraWQiOiJwcjhTaWE2dm9FZTcxNyttOWRiYXRlc3lJZkx6K3lIdDE4RGR5aGVodHZNPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIwNzYyZjdlZS1kZTIwLTRkYzUtODVlMS1iMTQ2NGZhNjE1ZjAiLCJkZXZpY2Vfa2V5IjoidXMtZWFzdC0xXzk4ZTZmMGU2LTU4ZGYtNDkxOS05ZDczLTIwYzE1ZDZmNjIxZCIsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy1lYXN0LTEuYW1hem9uYXdzLmNvbVwvdXMtZWFzdC0xX2IxTnl4WWNyMCIsImNsaWVudF9pZCI6IjY3MG1vN3NpODFwY2Mzc2Z1YjdvMTkxNGQ4Iiwib3JpZ2luX2p0aSI6Ijc1YWEyNjBhLTkxZTUtNDM2NS1iMGY2LTA0Y2Y4ZTEyYTdhOCIsImV2ZW50X2lkIjoiMDg2ZWYxNjYtNjY2OC00NzNkLTk2ZTEtODIzODQ5Y2MzNGQzIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiIsImF1dGhfdGltZSI6MTc2NDk0OTA1NywiZXhwIjoxNzY0OTY4Mzk0LCJpYXQiOjE3NjQ5NjQ3OTQsImp0aSI6IjBmZmRlZTA4LTQ3ZmEtNGIyOC1hYWM4LWFhNWVkZjNjYjg4YSIsInVzZXJuYW1lIjoiMDc2MmY3ZWUtZGUyMC00ZGM1LTg1ZTEtYjE0NjRmYTYxNWYwIn0.fyD8U285nBLta2az7X7GEO8AhKUQMs74h8SI9vep9SkCsciq2xm4YxJ_tjKWC90mv7CsSwmlRddHEyw88Koe-_7Ns89PZAhavKodnOkFsaEEEh3YDIoB-4H_mDVFPBDMc9wgYbrwvi25pkPUyckxtA9YbGGu9fkYlJGB7wqTDmZCdtbVy3Hd-6VFX4dGxQa-6LFZBX_NzZ_y43y-c9roiwgKSDGRn76bYOX5OELkcN1wjrx4rshqAOafL3LmpQi4AUa0ii_PdZTWS_e_ogf8uykPqrdxcWIj21t4GDw9M1wI10rsblvu-xcVltKh94SZ1kZfMYMplHL6O6X9qprh4Q"
    api_key = PENNSIEVE_API_KEY
    # api_key = os.environ.get('PENNSIEVE_API_KEY')
    if not api_key:
        logger.error("PENNSIEVE_API_KEY environment variable not set")
        sys.exit(1)

    # Determine dry_run mode (default is True, --execute makes it False)
    dry_run = not args.execute

    if dry_run:
        print("\n" + "="*60)
        print("DRY-RUN MODE (use --execute to actually delete)")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("⚠️  EXECUTE MODE - FILES WILL BE PERMANENTLY DELETED")
        print("="*60 + "\n")

    # Initialize manager
    manager = PennsieveDatasetManager(api_key, dry_run=dry_run)

    # Run deletion
    datasets_processed, files_deleted, files_failed = manager.delete_packages_by_pattern(
        dataset_prefix=args.prefix,
        dataset_list=args.datasets,
        file_patterns=args.file_pattern,
        force_reload=args.force_reload
    )

    # Exit with error code if any failures
    if files_failed > 0:
        sys.exit(1)

    # Exit with specific code if nothing was found
    if datasets_processed == 0:
        print("\nNo datasets matched the criteria.")
        sys.exit(2)

    if files_deleted == 0 and not dry_run:
        print("\nNo files matched the pattern in any dataset.")


if __name__ == '__main__':
    main()