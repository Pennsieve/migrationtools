#!/usr/bin/env python3
"""
Compile EEG JSON and Channels TSV files for upload.

Iterates through aligned eeg.json files and matches them with corresponding
channels.tsv files, then copies both to a compiled output directory.
"""

import shutil
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('compile_eeg_channels.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
EEGJSON_DIR = BASE_DIR / "checker/output/eegJson_check/eegjson_aligned"
CHANNELSTSV_DIR = BASE_DIR / "checker/output/channelTsv_check/channelstsv_matched"
OUTPUT_DIR = BASE_DIR / "checker/output/upload_check/compiled_eegchannels"


def compile_files(dry_run: bool = False):
    """
    Compile eeg.json and channels.tsv files into the output directory.

    Args:
        dry_run: If True, only print what would be done without copying files
    """
    # Find all *eeg.json files
    eeg_files = list(EEGJSON_DIR.rglob("*eeg.json"))
    logger.info(f"Found {len(eeg_files)} eeg.json files")

    success_count = 0
    missing_channels_count = 0
    error_count = 0

    for eeg_file in eeg_files:
        try:
            # Extract patient_id and session_dir from path
            # Path structure: .../sub-<patient_id>/<session_dir>/<filename>
            relative_path = eeg_file.relative_to(EEGJSON_DIR)
            parts = relative_path.parts

            if len(parts) < 3:
                logger.warning(f"Unexpected path structure: {eeg_file}")
                error_count += 1
                continue

            subject_dir = parts[0]  # sub-<patient_id>
            session_dir = parts[1]  # ses-<session>

            # Extract patient_id from subject_dir (remove 'sub-' prefix)
            if not subject_dir.startswith("sub-"):
                logger.warning(f"Invalid subject directory format: {subject_dir}")
                error_count += 1
                continue

            patient_id = subject_dir[4:]  # Remove 'sub-' prefix

            logger.info(f"Processing: patient={patient_id}, session={session_dir}")

            # Find corresponding channels.tsv file
            # channels.tsv naming: sub-<patient_id>_<session_dir>_task-prv_channels.tsv
            channels_filename = f"{subject_dir}_{session_dir}_task-prv_channels.tsv"
            channels_file = CHANNELSTSV_DIR / subject_dir / session_dir / channels_filename

            if not channels_file.exists():
                logger.warning(f"Channels file not found: {channels_file}")
                missing_channels_count += 1
                continue

            # Create output directory structure
            # output/upload_check/compiled_eegchannels/primary/sub-<patient_id>/<session_dir>/eeg/
            output_subdir = OUTPUT_DIR / "primary" / subject_dir / session_dir / "eeg"

            if not dry_run:
                output_subdir.mkdir(parents=True, exist_ok=True)

                # Copy eeg.json
                dest_eeg = output_subdir / eeg_file.name
                shutil.copy2(eeg_file, dest_eeg)
                logger.info(f"  Copied: {eeg_file.name} -> {dest_eeg}")

                # Copy channels.tsv
                dest_channels = output_subdir / channels_file.name
                shutil.copy2(channels_file, dest_channels)
                logger.info(f"  Copied: {channels_file.name} -> {dest_channels}")
            else:
                logger.info(f"  [DRY RUN] Would copy: {eeg_file.name}")
                logger.info(f"  [DRY RUN] Would copy: {channels_file.name}")
                logger.info(f"  [DRY RUN] To: {output_subdir}")

            success_count += 1

        except Exception as e:
            logger.error(f"Error processing {eeg_file}: {e}", exc_info=True)
            error_count += 1

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total eeg.json files found: {len(eeg_files)}")
    logger.info(f"Successfully compiled: {success_count}")
    logger.info(f"Missing channels.tsv: {missing_channels_count}")
    logger.info(f"Errors: {error_count}")

    if not dry_run:
        logger.info(f"\nOutput directory: {OUTPUT_DIR}")

    return success_count, missing_channels_count, error_count


def verify_prefix_match():
    """
    Verify that all eeg.json and channels.tsv files in the output directory
    have matching prefixes.

    Returns:
        Tuple of (matched_count, mismatched_pairs)
    """
    logger.info(f"\n{'='*60}")
    logger.info("VERIFYING PREFIX MATCHES")
    logger.info(f"{'='*60}")

    output_primary = OUTPUT_DIR / "primary"
    if not output_primary.exists():
        logger.warning("Output directory does not exist yet. Run without --dry-run first.")
        return 0, []

    matched_count = 0
    mismatched_pairs = []

    # Iterate through all eeg directories
    for eeg_dir in output_primary.rglob("eeg"):
        if not eeg_dir.is_dir():
            continue

        # Find eeg.json and channels.tsv files in this directory
        eeg_files = list(eeg_dir.glob("*_eeg.json"))
        channels_files = list(eeg_dir.glob("*_channels.tsv"))

        # Create prefix set for eeg files
        eeg_prefixes = {f.name.replace("_eeg.json", "") for f in eeg_files}

        # Check for each eeg file if there's a matching channels file
        for eeg_file in eeg_files:
            eeg_prefix = eeg_file.name.replace("_eeg.json", "")
            expected_channels = eeg_dir / f"{eeg_prefix}_channels.tsv"

            if expected_channels.exists():
                matched_count += 1
                logger.debug(f"Matched: {eeg_prefix}")
            else:
                mismatched_pairs.append({
                    "directory": str(eeg_dir),
                    "eeg_file": eeg_file.name,
                    "expected_channels": f"{eeg_prefix}_channels.tsv",
                    "available_channels": [f.name for f in channels_files]
                })
                logger.warning(f"Mismatch in {eeg_dir}:")
                logger.warning(f"  eeg.json: {eeg_file.name}")
                logger.warning(f"  Expected: {eeg_prefix}_channels.tsv")
                logger.warning(f"  Available: {[f.name for f in channels_files]}")

        # Check for orphan channels files (channels without matching eeg)
        for channels_file in channels_files:
            channels_prefix = channels_file.name.replace("_channels.tsv", "")
            if channels_prefix not in eeg_prefixes:
                logger.warning(f"Orphan channels.tsv in {eeg_dir}: {channels_file.name}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("VERIFICATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Matched pairs: {matched_count}")
    logger.info(f"Mismatched pairs: {len(mismatched_pairs)}")

    if mismatched_pairs:
        logger.error("PREFIX VERIFICATION FAILED - Some files have mismatched prefixes!")
        return matched_count, mismatched_pairs
    else:
        logger.info("PREFIX VERIFICATION PASSED - All eeg.json and channels.tsv files have matching prefixes!")
        return matched_count, mismatched_pairs


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Compile EEG JSON and Channels TSV files for upload'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without copying files'
    )

    args = parser.parse_args()

    # Verify input directories exist
    if not EEGJSON_DIR.exists():
        logger.error(f"EEG JSON directory does not exist: {EEGJSON_DIR}")
        sys.exit(1)

    if not CHANNELSTSV_DIR.exists():
        logger.error(f"Channels TSV directory does not exist: {CHANNELSTSV_DIR}")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be copied")

    compile_files(dry_run=args.dry_run)

    # Run verification after compiling (only if not dry run)
    if not args.dry_run:
        _, mismatched = verify_prefix_match()
        if mismatched:
            sys.exit(1)


if __name__ == '__main__':
    main()
