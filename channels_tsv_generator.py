#!/usr/bin/env python3
"""
Generate BIDS channels.tsv sidecar files.
Extracts channel information from EDF files and creates channels.tsv files.
"""

from sidecar.ChannelsTSV import ChannelsTSV


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
        for i in range(f.signals_in_file):
            label = f.getLabel(i)
            sampling_freq = f.getSampleFrequency(i)

            channels.append({
                "name": label,
                "sampling_frequency": sampling_freq,
            })

        f.close()
        return channels

    except ImportError:
        print("Warning: pyedflib not installed. Using placeholder channels.")
        # Placeholder channels from current code
        placeholder_channels = [
            "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
            "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
            "Fz", "Cz", "Pz", "EKG1", "EOG1"
        ]
        return [{"name": ch, "sampling_frequency": 2000} for ch in placeholder_channels]

    except Exception as e:
        print(f"Warning: Could not extract EDF channels: {e}")
        return []


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
    age = path_info['age']
    edf_file = path_info['edf_file']

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
            "low_cutoff": 0,
            "high_cutoff": 500,
            "notch": "n/a"
        })

    # Calculate bids_path: PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/
    bids_path = f"PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/"

    # Create custom filename: sub-<ptid>_ses-visit<age>m_task-prv_channels.tsv
    custom_filename = f"sub-{patient_id}_ses-visit{age}m_task-prv_channels.tsv"

    # Create sidecar
    channels_sidecar = ChannelsTSV(
        fields=rows,
        bids_path=bids_path,
        filename=custom_filename
    )

    # Validate and save
    try:
        if channels_sidecar.validate():
            saved_path = channels_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
