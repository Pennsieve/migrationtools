#!/usr/bin/env python3
"""
Generate BIDS channels.tsv sidecar files.
Extracts channel information from EDF files and creates channels.tsv files.
"""

import csv
from pathlib import Path
from typing import Dict, Any

from sidecar.channelsTSV import ChannelsTSV

MASTER_MIGRATION_METADATA = "origin/metadata/metadata.csv"


def read_csv_to_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Convert CSV into a dictionary indexed by (patient_id, session_dir).
    Skips the first row and uses the second row as header.
    Returns: dict like {('1W4Y', 'ses-visit03m'): {...row data...}, ...}
    """
    data = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        # Skip the first row (category row)
        next(f)
        # Now use DictReader which will use the current line (second row) as header
        reader = csv.DictReader(f)
        for row in reader:
            # Use PID1 as patient_id and session as session_dir
            patient_id = row.get("PID1")
            session_dir = row.get("session")
            if not patient_id or not session_dir:
                continue
            # Use (patient_id, session_dir) as composite key
            key = (patient_id.strip(), session_dir.strip())
            data[key] = {k: v for k, v in row.items()}
    return data


def extract_edf_channels(edf_file_path):
    """
    Extract channel information from EDF file for channels.tsv sidecar.

    Args:
        edf_file_path (str): Path to the EDF file

    Returns:
        list: List of channel dictionaries
    """
    try:
        import pyedflib
        f = pyedflib.EdfReader(edf_file_path)

        channels = []
        duration = f.getFileDuration()

        for i in range(f.signals_in_file):
            label = f.getLabel(i)
            # Calculate sampling frequency using total_samples / duration
            # (same method as eeg_json_generator.py)
            total_samples = f.getNSamples()[i]
            sampling_freq = total_samples / duration

            channels.append({
                "name": label,
                "sampling_frequency": sampling_freq,
            })

        f.close()
        return channels

    except ImportError:
        raise ImportError(
            "pyedflib is not installed. Please install it with: pip install pyedflib\n"
            "Or run: pip install -r requirements.txt"
        )
    except Exception as e:
        raise RuntimeError(f"Could not extract EDF channels from {edf_file_path}: {e}")


def handle_channels_tsv(path_info, output_base_dir):
    """
    Generate channels.tsv for a specific EEG session.
    Extracts channel information from the corresponding EDF file.

    Args:
        path_info: Dictionary with path information (patient_id, age, edf_file, etc.)
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """
    patient_id = path_info['patient_id']
    session_dir = path_info['session_dir']
    edf_file = path_info['edf_file']

    # Extract session name from session_dir path (e.g., "ses-visit24m")
    session_name = Path(session_dir).name

    # Load CSV metadata
    csv_path = Path(__file__).parent / MASTER_MIGRATION_METADATA
    data_map = {}
    if csv_path.exists():
        try:
            data_map = read_csv_to_dict(csv_path)
        except Exception as e:
            print(f"    Warning: Error reading CSV: {e}")

    patient_data = data_map.get((patient_id, session_name), {})

    # Get hardware filter values from CSV 
    low_cutoff = patient_data.get("hardwarefilters_min", "n/a") 
    high_cutoff = patient_data.get("hardwarefilters_max", "n/a") 

    # Extract channel information from EDF file
    channels_from_edf = extract_edf_channels(edf_file)

    # Use default sampling frequency if extraction fails
    default_sampling_freq = 2000

    # Create channel rows
    rows = []
    for channel_info in channels_from_edf:
        channel_name = channel_info["name"]

        # Skip "status" channel (case-insensitive)
        if channel_name.lower() == "status":
            continue

        sampling_freq = channel_info.get("sampling_frequency", default_sampling_freq)
        channel_type = ChannelsTSV.determine_channel_type(channel_name)

        rows.append({
            "name": channel_name,
            "type": channel_type,
            "units": "uV",
            "sampling_frequency": sampling_freq,
            "low_cutoff": low_cutoff,
            "high_cutoff": high_cutoff,
            "notch": "n/a"
        })

    # Calculate bids_path: PREVeNT Trial {patient_id}/primary/sub-{patient_id}/{session_name}/eeg/
    bids_path = f"PREVeNT Trial {patient_id}/primary/sub-{patient_id}/{session_name}/eeg/"

    # Create custom filename: sub-{patient_id}_{session_name}_task-prv_channels.tsv
    bids_filename = f"sub-{patient_id}_{session_name}_task-prv_channels.tsv"

    # Create sidecar
    channels_sidecar = ChannelsTSV(
        fields=rows,
        bids_path=bids_path,
        filename=bids_filename
    )

    # Validate and save
    try:
        if channels_sidecar.validate():
            saved_path = channels_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
