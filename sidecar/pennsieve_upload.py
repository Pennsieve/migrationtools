#!/usr/bin/env python3
"""
Pennsieve Bulk Upload Script

Automates the process of uploading multiple datasets to Pennsieve.
Each subfolder in the output directory represents a dataset.
"""

import subprocess
import sys
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pennsieve_upload.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PennsieveUploadError(Exception):
    """Custom exception for Pennsieve upload errors"""
    pass


def run_command(cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """
    Run a shell command and return the result.
    
    Args:
        cmd: Command and arguments as a list
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True
    )
    
    return result.returncode, result.stdout, result.stderr


def find_dataset_node_id(dataset_name: str) -> Optional[str]:
    """
    Find the Pennsieve node ID for a given dataset name.
    
    Args:
        dataset_name: Name of the dataset
        
    Returns:
        Node ID string (e.g., "N:dataset:8f9d9033-db09-4a5d-9c62-c85d7fbe5f10")
        or None if not found
    """
    logger.info(f"Looking up dataset: {dataset_name}")
    
    returncode, stdout, stderr = run_command(['pennsieve', 'dataset', 'find', dataset_name])
    
    if returncode != 0:
        logger.error(f"Failed to find dataset {dataset_name}: {stderr}, {stdout}")
        return None
    
    # Parse the output to extract the NODE ID
    # Looking for pattern like: N:dataset:8f9d9033-db09-4a5d-9c62-c85d7fbe5f10
    match = re.search(r'(N:dataset:[\w-]+)', stdout)
    
    if match:
        node_id = match.group(1)
        logger.info(f"Found node ID: {node_id}")
        return node_id
    else:
        logger.error(f"Could not parse node ID from output: {stdout}")
        return None


def set_active_dataset(node_id: str) -> bool:
    """
    Set the active dataset for upload operations.

    Args:
        node_id: The dataset node ID

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Setting active dataset: {node_id}")

    # Fixed: Command is 'pennsieve dataset use NODE_ID' not 'pennsieve dataset NODE_ID use'
    returncode, stdout, stderr = run_command(['pennsieve', 'dataset', 'use', node_id])

    logger.debug(f"set_active_dataset stdout: {stdout}")
    logger.debug(f"set_active_dataset stderr: {stderr}")
    logger.debug(f"set_active_dataset return code: {returncode}")

    if returncode != 0:
        logger.error(f"Failed to set active dataset: {stderr}")
        return False

    # Verify the active dataset was set correctly
    verify_returncode, verify_stdout, verify_stderr = run_command(['pennsieve', 'dataset'])
    logger.info(f"Active dataset after setting: {verify_stdout.strip()}")

    return True


def create_manifest(file_path: Path, target_path: Optional[str] = None) -> Optional[int]:
    """
    Create a Pennsieve manifest for a file.

    Args:
        file_path: Path to the file
        target_path: Optional target path in the dataset

    Returns:
        Manifest ID if successful, None otherwise
    """
    logger.info(f"Creating manifest for: {file_path}")

    full_path = Path(file_path).resolve()
    cmd = ['pennsieve', 'manifest', 'create', str(full_path)]
    if target_path and target_path != '.':
        cmd.extend(['-t', target_path])

    returncode, stdout, stderr = run_command(cmd)
    
    if returncode != 0:
        logger.error(f"Failed to create manifest: {stderr}")
        return None
    
    # Parse the manifest ID from output
    # Looking for: "Manifest ID: 6"
    match = re.search(r'Manifest ID:\s*(\d+)', stdout)
    
    if match:
        manifest_id = int(match.group(1))
        logger.info(f"Created manifest ID: {manifest_id}")
        return manifest_id
    else:
        logger.error(f"Could not parse manifest ID from output: {stdout}")
        return None


def add_to_manifest(manifest_id: int, file_path: Path) -> bool:
    """
    Add a file to an existing manifest.
    
    Args:
        manifest_id: The manifest ID
        file_path: Path to the file to add
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Adding to manifest {manifest_id}: {file_path}")
    full_path = Path(file_path).resolve()

    parts = Path(file_path).parts
    local_root = Path(parts[0]) / parts[1] 

    relative_to_root = Path(file_path).relative_to(local_root)
    remote_path = relative_to_root.parent
    
    cmd = ['pennsieve', 'manifest', 'add', str(manifest_id), str(full_path)]
    if str(remote_path) != '.':
        cmd.extend(['-t', str(remote_path)])

    returncode, stdout, stderr = run_command(cmd)
    if returncode != 0:
        logger.error(f"Failed to add file to manifest: {stderr}")
        return False
    
    logger.info(f"Successfully added file to manifest")
    return True


def upload_manifest(manifest_id: int) -> bool:
    """
    Upload files using the specified manifest.
    
    Args:
        manifest_id: The manifest ID to upload
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Uploading manifest: {manifest_id}")
    
    returncode, stdout, stderr = run_command(
        ['pennsieve', 'upload', 'manifest', str(manifest_id)],
        capture_output=True
    )

    logger.info(f"Upload output:{stdout}")
    logger.info(returncode)
    
    if returncode != 0:
        logger.error(f"Failed to upload manifest: {stderr}")
        return False
    
    logger.info(f"Successfully uploaded manifest {manifest_id}")
    return True


def get_all_files(dataset_dir: Path) -> List[Path]:
    """
    Get all files in a directory recursively, excluding hidden files.
    
    Args:
        dataset_dir: Directory to search
        
    Returns:
        List of file paths, excluding hidden files
    """
    files = []
    
    for item in dataset_dir.rglob('*'):
        # Skip directories
        if item.is_dir():
            continue
        
        # Skip hidden files (starting with .)
        if any(part.startswith('.') for part in item.parts):
            logger.debug(f"Skipping hidden file: {item}")
            continue
        
        files.append(item)
    
    return files


def process_dataset(dataset_dir: Path, dry_run: bool = False, file_patterns: Optional[List[str]] = None) -> Optional[bool]:
    """
    Process a single dataset: find node ID, create manifest, add files, upload.

    Args:
        dataset_dir: Path to the dataset directory
        dry_run: If True, don't actually upload
        file_patterns: Optional list of patterns to match in filenames (e.g., ['ses-postimplant', 'electrodes.tsv'])

    Returns:
        True if successful, False if failed, None if skipped
    """
    dataset_name = dataset_dir.name
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing dataset: {dataset_name}")
    logger.info(f"{'='*60}")

    # Step 1: Find the dataset node ID
    node_id = find_dataset_node_id(dataset_name)
    if not node_id:
        logger.warning(f"Dataset not found in Pennsieve, skipping: {dataset_name}")
        return None  # Return None to indicate "skipped" rather than "failed"

    # Step 2: Set active dataset
    if not dry_run:
        if not set_active_dataset(node_id):
            logger.error(f"Could not set active dataset: {dataset_name}")
            return False
    else:
        logger.info(f"[DRY RUN] Would set active dataset: {node_id}")

    # Step 3: Get files to upload
    all_files = get_all_files(dataset_dir)

    # Apply file pattern filter if specified
    if file_patterns:
        files_to_upload = [f for f in all_files if any(p in f.name for p in file_patterns)]
        logger.info(f"Filtering for patterns: {file_patterns}")
        logger.info(f"Found {len(files_to_upload)} matching files")
        for f in files_to_upload:
            logger.info(f"  - {f.relative_to(dataset_dir)}")

        if not files_to_upload:
            logger.warning(f"No files matched the patterns in {dataset_name}")
            return None
    else:
        # Original behavior: require dataset_description.json and upload all files
        dataset_description = dataset_dir / 'dataset_description.json'
        if not dataset_description.exists():
            logger.error(f"dataset_description.json not found in {dataset_dir}")
            return False
        files_to_upload = all_files

    if not files_to_upload:
        logger.warning(f"No files to upload for {dataset_name}")
        return None

    # Step 4: Create manifest with the first file
    first_file = files_to_upload[0]
    # Calculate target path relative to dataset dir
    relative_path = first_file.relative_to(dataset_dir)
    target_path = str(relative_path.parent) if relative_path.parent != Path('.') else None

    if not dry_run:
        manifest_id = create_manifest(first_file, target_path)
        if manifest_id is None:
            logger.error("Failed to create manifest")
            return False
    else:
        manifest_id = 999  # Dummy ID for dry run
        logger.info(f"[DRY RUN] Would create manifest with: {first_file} (target: {target_path or 'root'})")

    # Step 5: Add remaining files to manifest
    remaining_files = files_to_upload[1:]
    logger.info(f"Adding {len(remaining_files)} additional files to manifest")

    for file_path in remaining_files:
        if not dry_run:
            if not add_to_manifest(manifest_id, file_path):
                logger.error(f"Failed to add file: {file_path}")
                return False
        else:
            logger.info(f"[DRY RUN] Would add to manifest: {file_path}")

    # Step 6: Upload the manifest
    if not dry_run:
        logger.info("NOTE: Pennsieve does not overwrite files. If files already exist, duplicates will be created with numbered suffixes.")
        if not upload_manifest(manifest_id):
            logger.error("Failed to upload manifest")
            return False
    else:
        logger.info(f"[DRY RUN] Would upload manifest {manifest_id}")
        logger.info("[DRY RUN] NOTE: Pennsieve does not overwrite existing files - duplicates would be created if files already exist")

    logger.info(f"Successfully processed dataset: {dataset_name}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Bulk upload datasets to Pennsieve',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on all datasets
  %(prog)s /path/to/output --datasets "*" --dry-run

  # Upload specific datasets
  %(prog)s /path/to/output --datasets PennEPI00001 PennEPI00002

  # Upload all datasets (CAREFUL!)
  %(prog)s /path/to/output --datasets "*"

  # Upload only files matching a pattern (preserves directory structure)
  %(prog)s /path/to/output --datasets PennEPI00001 --pattern ses-postimplant_space-MNI152NLin6ASym
        """
    )
    
    parser.add_argument(
        'output_dir',
        type=Path,
        help='Path to the output directory containing dataset folders'
    )
    
    parser.add_argument(
        '--datasets',
        nargs='+',
        required=True,
        help='Dataset names to process. Use "*" for all, or list specific names'
    )
    
    parser.add_argument(
        '--pattern',
        nargs='+',
        default=None,
        help='Only upload files containing any of these patterns in their name (e.g., --pattern ses-postimplant_space-MNI152NLin6ASym electrodes.tsv). Paths are preserved.'
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
    
    # Validate output directory
    if not args.output_dir.exists():
        logger.error(f"Output directory does not exist: {args.output_dir}")
        sys.exit(1)
    
    if not args.output_dir.is_dir():
        logger.error(f"Output path is not a directory: {args.output_dir}")
        sys.exit(1)
    
    # Determine which datasets to process
    if args.datasets == ["*"]:
        # Process all subdirectories
        dataset_dirs = [d for d in args.output_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        logger.info(f"Processing all {len(dataset_dirs)} datasets")
    else:
        # Process specific datasets
        dataset_dirs = [args.output_dir / name for name in args.datasets]
        # Validate they exist
        for d in dataset_dirs:
            if not d.exists():
                logger.error(f"Dataset directory does not exist: {d}")
                sys.exit(1)
    
    if not dataset_dirs:
        logger.warning("No datasets to process")
        sys.exit(0)
    
    if args.dry_run:
        logger.info("\n" + "="*60)
        logger.info("DRY RUN MODE - No actual uploads will occur")
        logger.info("="*60 + "\n")
    
    # Process each dataset
    success_count = 0
    failure_count = 0
    skipped_count = 0
    
    for dataset_dir in dataset_dirs:
        try:
            result = process_dataset(dataset_dir, dry_run=args.dry_run, file_patterns=args.pattern)
            if result is True:
                success_count += 1
            elif result is None:
                skipped_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"Unexpected error processing {dataset_dir.name}: {e}", exc_info=True)
            failure_count += 1
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total datasets processed: {len(dataset_dirs)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Failed: {failure_count}")
    
    if failure_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()