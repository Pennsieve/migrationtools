#!/usr/bin/env python3

import csv
from pathlib import Path
from typing import Dict, Any

from sidecar.EegJSON import EegJSON
from sidecar.ChannelsTSV import ChannelsTSV

MASTER_MIGRATION_METADATA = "input/metadata/dummy.csv"

# ==== helper functions to fetch info from EDF files and Spreadsheet ====
def extract_edf_metadata(edf_file_path):
    """
    Extract metadata from EDF file for eeg.json sidecar.

    Args: edf_file_path (str): Path to the EDF file
    Returns: dict: Dictionary containing EDF metadata
    """
    try:
        import pyedflib
        f = pyedflib.EdfReader(edf_file_path)

        # task 1: fetch channels counts by type
        channel_counts = {"EEG": 0, "ECG": 0, "EMG": 0, "EOG": 0, "MISC": 0, "TRIG": 0}
        for i in range(f.signals_in_file):
            label = f.getLabel(i)
            
            # Skip "status" channel (case-insensitive)
            if label.lower() == "status":
                continue
                
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

        # task 2: fetch sampling frequency and duration
        total_samples = f.getNSamples()[0]  # samples from first channel
        duration = f.getFileDuration()
        sampling_frequency = total_samples / duration

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
            "SamplingFrequency": 2000,
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


def read_csv_to_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Convert CSV into a dictionary indexed by (patient_id, age).
    Returns: dict like {('1W4Y', '3'): {...row data...}, ('1W4Y', '4.5'): {...}, ...}
    """
    data = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id = row.get("patient_id")
            age = row.get("Age")
            if not patient_id or not age:
                continue
            # Use (patient_id, age) as composite key
            key = (patient_id.strip(), age.strip())
            data[key] = {k: v for k, v in row.items() if k not in ("patient_id", "Age")}
    return data


# ==== main function ====
def handle_eeg_json(path_info, output_base_dir):
    """
    Generate eeg.json sidecar.
    Extracts metadata from EDF file and CSV, then creates sidecar.

    Args:
        path_info: Dictionary with path information (patient_id, age, edf_file, etc.)
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """

    # ---- Extract path info
    patient_id = path_info['patient_id']
    age = path_info['age']
    edf_file = path_info['edf_file']

    bids_path = f"PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/"
    bids_filename = f"sub-{patient_id}_ses-visit{age}m_task-prv_eeg.json"

    # ---- Nested helper functions to extract metadata
    def get_edf_metadata():
        """Extract metadata from EDF file."""
        return extract_edf_metadata(edf_file)

    def get_csv_data_map():
        """Load and return the CSV data map indexed by patient_id."""
        csv_path = Path(__file__).parent / MASTER_MIGRATION_METADATA
        if not csv_path.exists():
            print(f"    Warning: CSV metadata file not found at {csv_path}")
            return {}
        try:
            return read_csv_to_dict(csv_path)
        except Exception as e:
            print(f"    Warning: Error reading CSV: {e}")
            return {}

    # ---- Get data from sources
    edf_metadata = get_edf_metadata()
    data_map = get_csv_data_map()
    patient_data = data_map.get((patient_id, str(age)), {})

    if not patient_data:
        print(f"    Warning: No CSV metadata found for patient {patient_id}")

    # ---- Build eeg.json data dictionary explicitly (like createIEEGDataSidecar)
    eeg_data = {
        # Required fields - from constants and EDF
        "TaskName": "PRV",
        "TaskDescription": "All video EEG studies will be recorded for one hour, incorporating both 20mins of sleep and wakefulness. Recordings can be up to 80min to attempt to capture sleep",
        "EEGReference": "Slightly anterior and slightly left of the Cz electrode",
        "EEGGround": "Slightly anterior and slightly right of the Cz electrode",
        "SamplingFrequency": edf_metadata.get("SamplingFrequency", -1),
        "PowerLineFrequency": 60,
        "SoftwareFilters": {
            "Anti-aliasing filter": {
                "half-amplitude cutoff (Hz)": 500
            }
        },

        # Recommended fields - from CSV and EDF
        "InstitutionName": patient_data.get("InstitutionName", ""),
        "Manufacturer": patient_data.get("Manufacturer", ""),
        "EEGChannelCount": edf_metadata.get("EEGChannelCount", -1),
        "ECGChannelCount": edf_metadata.get("ECGChannelCount", -1),
        "EMGChannelCount": edf_metadata.get("EMGChannelCount", -1),
        "EOGChannelCount": edf_metadata.get("EOGChannelCount", -1),
        "MiscChannelCount": edf_metadata.get("MiscChannelCount", -1),
        "TriggerChannelCount": edf_metadata.get("TriggerChannelCount", -1),
        "RecordingDuration": edf_metadata.get("RecordingDuration", -1),
        "RecordingType": "continuous",
        "EEGPlacementScheme": patient_data.get("EEGPlacementScheme", ""),
        "HardwareFilters": {
            "Highpass filter": {
                "cutoff (Hz)": float(patient_data.get("hardware_filter_low", 0)) if patient_data.get("hardware_filter_low") else 0
            },
            "Lowpass filter": {
                "cutoff (Hz)": float(patient_data.get("hardware_filter_high", 0)) if patient_data.get("hardware_filter_high") else 0
            }
        },

        # Optional fields - from CSV
        # "ManufacturerModelName": patient_data.get("model", ""),
        "SubjectArtefactDescription": patient_data.get("SubjectArtefactDescription", ""),
    }

    # ---- Create sidecar and save
    eeg_sidecar = EegJSON(
        fields=eeg_data,
        bids_path=bids_path,
        filename=bids_filename
    )

    try:
        if eeg_sidecar.validate():
            saved_path = eeg_sidecar.save(output_dir=output_base_dir)
            print(f"    ✓ Saved: {saved_path}")
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
