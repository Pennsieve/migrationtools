#!/usr/bin/env python3
"""
Generate BIDS sidecar files for the reorganized EEG data.
Discovers the BIDS structure and creates appropriate sidecars.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from sidecar.EegJSON import EegJSON
from sidecar.SessionsTSV import SessionsTSV
from sidecar.ChannelsTSV import ChannelsTSV

import sys, os, pprint
print("PYTHON EXE:", sys.executable)
print("PYTHONPATH env:", os.environ.get("PYTHONPATH"))
pprint.pp(sys.path[:10])

# ==== Helper Functions ==== #

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
        
        # Import the ChannelsTSV class to use its determine_channel_type method
        from sidecar.ChannelsTSV import ChannelsTSV
        
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


def find_bids_path(output_dir):
    """
    Find all EEG session directories in the output folder.
    Returns list of tuples: (patient_id, age, eeg_dir_path, edf_file_path)
    """
    path = []
    output_path = Path(output_dir)
    
    # Pattern: output/PRV-{patient_id}/primary/sub-{patient_id}/ses-visit{age}m/eeg/
    for dataset_dir in output_path.glob("PRV-*"):
        patient_id = dataset_dir.name.replace("PRV-", "")
        
        # Navigate to subject directory
        subject_dir = dataset_dir / "primary" / f"sub-{patient_id}"
        
        if not subject_dir.exists():
            continue
        
        # Find all session directories
        for session_dir in subject_dir.glob("ses-visit*m"):
            # Extract age from session name (ses-visit15m -> 15)
            age = session_dir.name.replace("ses-visit", "").replace("m", "")
            
            # Check for eeg directory
            eeg_dir = session_dir / "eeg"
            if eeg_dir.exists():
                # Find EDF file in this directory
                edf_files = list(eeg_dir.glob("*.edf"))
                if edf_files:
                    path.append({
                        'patient_id': patient_id,
                        'age': age,
                        'subject_dir': str(subject_dir),
                        'session_dir': str(session_dir),
                        'eeg_dir': str(eeg_dir),
                        'edf_file': str(edf_files[0])
                    })
    
    return path



# ==== Main Sidecar Generation Function ==== #
def handle_eeg_json(path_info, output_base_dir):
    """
    Generate eeg.json sidecar.
    Extracts metadata from the corresponding EDF file.
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


def handle_sessions_tsv(patient_id, sessions_data, output_base_dir):
    """
    Generate sessions.tsv for a specific patient.
    
    Args:
        patient_id: Patient identifier (e.g., "4ZHY")
        sessions_data: List of dicts with 'age' for each session
        output_base_dir: Base output directory
    
    Returns:
        bool: True if successful, False otherwise
    """    
    # Sort sessions by age
    sorted_sessions = sorted(sessions_data, key=lambda x: float(x['age']))
    
    # Create TSV rows
    rows = []
    for i, session in enumerate(sorted_sessions):
        age = float(session['age'])
        # Baseline only if it's the smallest age AND age is between 1.5 to 6 months
        if i == 0 and 1.5 <= age <= 6:
            visit_type = "baseline"
        else:
            visit_type = "followup"
        
        rows.append({
            "session": f"ses-visit{int(age)}m",
            "visit_type": visit_type,
            "age_in_months": age
        })
    
    # Calculate bids_path: PRV-{patient_id}/primary/sub-{patient_id}/
    bids_path = f"PRV-{patient_id}/primary/sub-{patient_id}/"
    
    # Create custom filename
    custom_filename = f"sub-{patient_id}_sessions.tsv"
    
    # Create sidecar
    sessions_sidecar = SessionsTSV(
        fields=rows,
        bids_path=bids_path,
        filename=custom_filename
    )
    
    # Validate and save
    try:
        if sessions_sidecar.validate():
            saved_path = sessions_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


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




# ==== Main Execution ==== #
def main():
    """Main execution function."""
    script_dir = Path(__file__).parent
    output_dir = script_dir / "output"
        
    # Find all EEG paths
    print("\n1. Discovering EEG pathes...")
    pathes = find_bids_path(output_dir)
    print(f"   Found {len(pathes)} session(s)")
    
    if not pathes:
        print("   No EEG path found. Exiting.")
        return 0
    
    # Group sessions by patient for sessions.tsv generation
    sessions_by_patient = defaultdict(list)
    for path in pathes:
        sessions_by_patient[path['patient_id']].append({'age': path['age']})
    
    # Generate _eeg.json for each path
    print("\n2. Generating _eeg.json sidecars...")
    successful_eeg = 0
    failed_eeg = 0
    
    for path in pathes:
        if handle_eeg_json(path, str(output_dir)):
            successful_eeg += 1
        else:
            failed_eeg += 1
    
    # Generate _channels.tsv for each path
    print("\n3. Generating _channels.tsv sidecars...")
    successful_channels = 0
    failed_channels = 0
    
    for path in pathes:
        if handle_channels_tsv(path, str(output_dir)):
            successful_channels += 1
        else:
            failed_channels += 1
    
    # Generate sessions.tsv for each patient
    print("\n4. Generating sessions.tsv sidecars...")
    successful_sessions = 0
    failed_sessions = 0
    
    for patient_id, sessions in sessions_by_patient.items():
        if handle_sessions_tsv(patient_id, sessions, str(output_dir)):
            successful_sessions += 1
        else:
            failed_sessions += 1
    
    # Summary
    print(f"EEG JSON: {successful_eeg} successful, {failed_eeg} failed")
    print(f"Channels TSV: {successful_channels} successful, {failed_channels} failed")
    print(f"Sessions TSV: {successful_sessions} successful, {failed_sessions} failed")
    
    return 0 if (failed_eeg == 0 and failed_channels == 0 and failed_sessions == 0) else 1

if __name__ == "__main__":
    sys.exit(main())
