#!/usr/bin/env python3
"""
Generate BIDS eeg.json sidecar files.
Extracts metadata from EDF files and creates eeg.json files.
"""

from sidecar.EegJSON import EegJSON
from sidecar.ChannelsTSV import ChannelsTSV


def extract_edf_metadata(edf_file_path):
    """
    Extract metadata from EDF file for eeg.json sidecar.

    Args:
        edf_file_path (str): Path to the EDF file

    Returns:
        dict: Dictionary containing EDF metadata
    """
    try:
        import pyedflib
        f = pyedflib.EdfReader(edf_file_path)

        # Count different channel types using the same logic as ChannelsTSV
        channel_counts = {"EEG": 0, "ECG": 0, "EMG": 0, "EOG": 0, "MISC": 0, "TRIG": 0}

        # Get sampling frequency using your calculation method (more robust)
        total_samples = f.getNSamples()[0]  # samples from first channel
        duration = f.getFileDuration()
        sampling_frequency = total_samples / duration

        # Alternative: EDF header method (also works since all channels have same rate)
        # sampling_frequency = f.getSampleFrequency(0)

        for i in range(f.signals_in_file):
            label = f.getLabel(i)
            # Use the same classification logic as ChannelsTSV
            channel_type = ChannelsTSV.determine_channel_type(label)

            # Map channel types to our counting categories
            if channel_type == "EEG":
                channel_counts["EEG"] += 1
            elif channel_type == "ECG":
                channel_counts["ECG"] += 1
            elif channel_type == "EMG":
                channel_counts["EMG"] += 1
            elif channel_type == "EOG":
                channel_counts["EOG"] += 1
            else:  # "MISC" and others
                channel_counts["MISC"] += 1

        metadata = {
            "SamplingFrequency": sampling_frequency,
            "RecordingDuration": f.getFileDuration(),
            "EEGChannelCount": channel_counts["EEG"],
            "ECGChannelCount": channel_counts["ECG"],
            "EMGChannelCount": channel_counts["EMG"],
            "EOGChannelCount": channel_counts["EOG"],
            "MiscChannelCount": channel_counts["MISC"],
            "TriggerChannelCount": channel_counts["TRIG"],
        }

        f.close()
        return metadata

    except ImportError:
        print("Warning: pyedflib not installed. Using placeholder values.")
        return {
            "SamplingFrequency": 2000,  # Placeholder
            "RecordingDuration": 0,
            "EEGChannelCount": 0,
            "ECGChannelCount": 0,
            "EMGChannelCount": 0,
            "EOGChannelCount": 0,
            "MiscChannelCount": 0,
            "TriggerChannelCount": 0,
        }
    except Exception as e:
        print(f"Warning: Could not extract EDF metadata: {e}")
        return {}


def handle_eeg_json(path_info, output_base_dir):
    """
    Generate eeg.json sidecar.
    Extracts metadata from the corresponding EDF file.

    Args:
        path_info: Dictionary with path information (patient_id, age, edf_file, etc.)
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """
    patient_id = path_info['patient_id']
    age = path_info['age']
    subject_dir = path_info['subject_dir']
    session_dir = path_info['session_dir']
    eeg_dir = path_info['eeg_dir']
    edf_file = path_info['edf_file']

    # Extract metadata from EDF file
    edf_data = extract_edf_metadata(edf_file)

    # Calculate the bids_path relative to output_base_dir
    # We want: PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/
    bids_path = f"PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/"

    # Create custom filename following new naming format: sub-<ptid>_ses-visit<age>m_task-prv_eeg.json
    custom_filename = f"sub-{patient_id}_ses-visit{age}m_task-prv_eeg.json"

    # Create sidecar with extracted data (or defaults)
    eeg_sidecar = EegJSON(
        fields=edf_data,
        bids_path=bids_path,
        filename=custom_filename
    )

    # Validate and save
    try:
        if eeg_sidecar.validate():
            saved_path = eeg_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
