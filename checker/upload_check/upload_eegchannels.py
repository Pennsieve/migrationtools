#!/usr/bin/env python3
"""
Upload EEG JSON and Channels TSV files to Pennsieve

This script uploads the compiled eeg.json and channels.tsv files from
checker/output/upload_check/compiled_eegchannels/ to the corresponding
PREVeNT Trial datasets on Pennsieve.

File structure expected:
  compiled_eegchannels/primary/sub-<patient_id>/ses-<visit>/eeg/
    - sub-<patient_id>_ses-<visit>_task-prv_channels.tsv
    - sub-<patient_id>_ses-<visit>_task-prv_eeg.json

Uploads to:
  Dataset: "PREVeNT Trial <patient_id>"
  Path: primary/sub-<patient_id>/ses-<visit>/eeg/
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import argparse

# Import functions from pennsieve_upload.py
from pennsieve_upload import (
    run_command,
    find_dataset_node_id,
    set_active_dataset,
    create_manifest,
    add_to_manifest,
    upload_manifest,
    logger
)

# Reconfigure logging for this script
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload_eegchannels.log'),
        logging.StreamHandler(sys.stdout)
    ]
)


def parse_file_path(file_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse patient_id and session from file path.

    Expected path format:
    .../primary/sub-<patient_id>/ses-<visit>/eeg/<filename>

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (patient_id, session_dir) or (None, None) if parsing fails
    """
    parts = file_path.parts

    patient_id = None
    session_dir = None

    # Only look at directory parts (exclude the filename)
    dir_parts = parts[:-1]

    for part in dir_parts:
        if part.startswith('sub-'):
            patient_id = part[4:]  # Remove 'sub-' prefix
        elif part.startswith('ses-'):
            session_dir = part

    return patient_id, session_dir


def get_eeg_files(source_dir: Path) -> List[Path]:
    """
    Get all eeg.json and channels.tsv files from the source directory.

    Args:
        source_dir: Path to compiled_eegchannels directory

    Returns:
        List of file paths
    """
    files = []

    for file_path in source_dir.rglob('*'):
        if file_path.is_file():
            if file_path.name.endswith('_eeg.json') or file_path.name.endswith('_channels.tsv'):
                files.append(file_path)

    return sorted(files)


def group_files_by_dataset(files: List[Path]) -> dict:
    """
    Group files by their target dataset.

    Args:
        files: List of file paths

    Returns:
        Dictionary mapping patient_id to list of (file_path, target_path) tuples
    """
    grouped = {}

    for file_path in files:
        patient_id, session_dir = parse_file_path(file_path)

        if not patient_id or not session_dir:
            logger.warning(f"Could not parse patient_id/session from: {file_path}")
            continue

        # Target path in Pennsieve: primary/sub-<patient_id>/ses-<visit>/eeg
        target_path = f"primary/sub-{patient_id}/{session_dir}/eeg"

        if patient_id not in grouped:
            grouped[patient_id] = []

        grouped[patient_id].append((file_path, target_path))

    return grouped


def upload_patient_files(
    patient_id: str,
    files_with_targets: List[Tuple[Path, str]],
    dry_run: bool = False
) -> Optional[bool]:
    """
    Upload files for a single patient to their PREVeNT Trial dataset.

    Args:
        patient_id: The patient ID (e.g., "13UL")
        files_with_targets: List of (file_path, target_path) tuples
        dry_run: If True, don't actually upload

    Returns:
        True if successful, False if failed, None if skipped
    """
    dataset_name = f"PREVeNT Trial {patient_id}"

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing patient: {patient_id}")
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Files to upload: {len(files_with_targets)}")
    logger.info(f"{'='*60}")

    # Step 1: Find the dataset node ID
    node_id = find_dataset_node_id(dataset_name)
    if not node_id:
        logger.warning(f"Dataset not found in Pennsieve: {dataset_name}")
        return None

    # Step 2: Set active dataset
    if not dry_run:
        if not set_active_dataset(node_id):
            logger.error(f"Could not set active dataset: {dataset_name}")
            return False
    else:
        logger.info(f"[DRY RUN] Would set active dataset: {node_id}")

    # Step 3: Create manifest with first file
    first_file, first_target = files_with_targets[0]

    if not dry_run:
        manifest_id = create_manifest(first_file, first_target)
        if manifest_id is None:
            logger.error(f"Failed to create manifest for {first_file}")
            return False
    else:
        manifest_id = 999
        logger.info(f"[DRY RUN] Would create manifest with: {first_file}")
        logger.info(f"[DRY RUN]   Target path: {first_target}")

    # Step 4: Add remaining files to manifest
    for file_path, target_path in files_with_targets[1:]:
        if not dry_run:
            # For subsequent files, we need to use a custom add since
            # target paths may differ per file
            logger.info(f"Adding to manifest {manifest_id}: {file_path}")
            full_path = Path(file_path).resolve()

            cmd = ['pennsieve', 'manifest', 'add', str(manifest_id), str(full_path)]
            if target_path and target_path != '.':
                cmd.extend(['-t', target_path])

            returncode, stdout, stderr = run_command(cmd)
            if returncode != 0:
                logger.error(f"Failed to add file to manifest: {stderr}")
                return False

            logger.info(f"Successfully added file to manifest")
        else:
            logger.info(f"[DRY RUN] Would add to manifest: {file_path}")
            logger.info(f"[DRY RUN]   Target path: {target_path}")

    # Step 5: Upload the manifest
    if not dry_run:
        logger.info("NOTE: Pennsieve does not overwrite files. If files already exist, duplicates will be created.")
        if not upload_manifest(manifest_id):
            logger.error("Failed to upload manifest")
            return False
    else:
        logger.info(f"[DRY RUN] Would upload manifest {manifest_id}")

    logger.info(f"Successfully processed patient: {patient_id}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Upload compiled eeg.json and channels.tsv files to Pennsieve',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be uploaded
  %(prog)s --dry-run

  # Dry run for specific patients
  %(prog)s --patients 13UL 15EC --dry-run

  # Upload all patients
  %(prog)s

  # Upload specific patients
  %(prog)s --patients 13UL 15EC 166V

  # Use custom source directory
  %(prog)s --source /path/to/compiled_eegchannels
        """
    )

    default_source = Path(__file__).parent.parent / 'output' / 'upload_check' / 'compiled_eegchannels'

    parser.add_argument(
        '--source',
        type=Path,
        default=default_source,
        help=f'Path to compiled_eegchannels directory (default: {default_source})'
    )

    parser.add_argument(
        '--patients',
        nargs='+',
        default=None,
        help='Specific patient IDs to process (e.g., 13UL 15EC). If not specified, processes all.'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without actually uploading (recommended for testing)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate source directory
    if not args.source.exists():
        logger.error(f"Source directory does not exist: {args.source}")
        sys.exit(1)

    logger.info(f"Source directory: {args.source}")

    # Get all eeg.json and channels.tsv files
    files = get_eeg_files(args.source)
    logger.info(f"Found {len(files)} files to process")

    if not files:
        logger.warning("No eeg.json or channels.tsv files found")
        sys.exit(0)

    # Group files by patient/dataset
    grouped = group_files_by_dataset(files)
    logger.info(f"Found {len(grouped)} patients to process")

    # Filter by specific patients if requested
    if args.patients:
        filtered = {k: v for k, v in grouped.items() if k in args.patients}
        if not filtered:
            logger.error(f"No matching patients found for: {args.patients}")
            logger.info(f"Available patients: {list(grouped.keys())}")
            sys.exit(1)
        grouped = filtered
        logger.info(f"Filtered to {len(grouped)} patients: {list(grouped.keys())}")

    if args.dry_run:
        logger.info("\n" + "="*60)
        logger.info("DRY RUN MODE - No actual uploads will occur")
        logger.info("="*60 + "\n")

    # Process each patient
    success_count = 0
    failure_count = 0
    skipped_count = 0

    for patient_id, files_with_targets in sorted(grouped.items()):
        try:
            result = upload_patient_files(patient_id, files_with_targets, dry_run=args.dry_run)
            if result is True:
                success_count += 1
            elif result is None:
                skipped_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"Unexpected error processing patient {patient_id}: {e}", exc_info=True)
            failure_count += 1

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total patients: {len(grouped)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Skipped (dataset not found): {skipped_count}")
    logger.info(f"Failed: {failure_count}")

    if failure_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
