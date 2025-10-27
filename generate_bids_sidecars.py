#!/usr/bin/env python3
"""
Generate BIDS sidecar files for the reorganized EEG data.
Discovers the BIDS structure and creates appropriate sidecars.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from sidecar.eegJSON import eegJSON
from sidecar.sessionsTSV import SessionsTSV
from sidecar.channelsTSV import ChannelsTSV

# ==== Helper Functions ==== #
def find_bids_path(output_dir):
    """
    Find all EEG session directories in the output folder.
    Returns list of tuples: (patient_id, age, eeg_dir_path, edf_file_path)
    """
    path = []
    output_path = Path(output_dir)
    
    # Pattern: output/PRV-{patient_id}/primary/sub-PRV-{patient_id}/ses-visit-m{age}/eeg/
    for dataset_dir in output_path.glob("PRV-*"):
        patient_id = dataset_dir.name.replace("PRV-", "")
        
        # Navigate to subject directory
        subject_dir = dataset_dir / "primary" / f"sub-PRV-{patient_id}"
        
        if not subject_dir.exists():
            continue
        
        # Find all session directories
        for session_dir in subject_dir.glob("ses-visit-m*"):
            # Extract age from session name (ses-visit-m15 -> 15)
            age = session_dir.name.replace("ses-visit-m", "")
            
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
    For now, uses default values for testing.
    """
    patient_id = path_info['patient_id']    
    age = path_info['age']
    subject_dir = path_info['subject_dir']
    session_dir = path_info['session_dir']
    #eeg_dir = path_info['eeg_dir']
    #edf_file = path_info['edf_file']
        
    # For testing: use placeholder values (no EDF extraction yet)
    # TODO: Replace with actual EDF extraction
    edf_data = {
        "SamplingFrequency": 2000,  # Placeholder for testing
    }
    
    # TODO: Uncomment this when ready to extract from EDF
    '''
    import pyedflib
    f = pyedflib.EdfReader(edf_file)
    edf_data = {
        "SamplingFrequency": f.getSampleFrequency(0),
        "RecordingDuration": f.getFileDuration(),
        "EEGChannelCount": f.signals_in_file,
    }
    f.close()
    '''
    
    # Calculate the bids_path relative to output_base_dir
    # We want: PRV-{patient_id}/primary/sub-PRV-{patient_id}/ses-visit-m{age}/eeg/
    bids_path = f"PRV-{patient_id}/primary/sub-PRV-{patient_id}/ses-visit-m{age}/eeg/"
    
    # Create custom filename following BIDS format: sub-PRV-<ptid>-<age>_task-rest_eeg.json
    custom_filename = f"sub-PRV-{patient_id}-{age}_task-rest_eeg.json"
    
    # Create sidecar with extracted data (or defaults)
    eeg_sidecar = eegJSON(
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
        age = session['age']
        # First session is baseline, rest are followup
        visit_type = "baseline" if i == 0 else "followup"
        
        rows.append({
            "session": f"ses-visit-m{age}",
            "visit_type": visit_type,
            "age_in_months": float(age)
        })
    
    # Calculate bids_path: PRV-{patient_id}/primary/sub-PRV-{patient_id}/
    bids_path = f"PRV-{patient_id}/primary/sub-PRV-{patient_id}/"
    
    # Create custom filename
    custom_filename = f"sub-PRV-{patient_id}_sessions.tsv"
    
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
    
    Args:
        path_info: Dictionary with path information (patient_id, age, edf_file, etc.)
        output_base_dir: Base output directory
    
    Returns:
        bool: True if successful, False otherwise
    """
    patient_id = path_info['patient_id']
    age = path_info['age']
    edf_file = path_info['edf_file']
    
    # TODO: Replace with actual EDF extraction using pyedflib
    # For now, use placeholder channels
    placeholder_channels = [
        "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", 
        "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
        "Fz", "Cz", "Pz", "EKG1", "EOG1"
    ]
    
    # TODO: Uncomment when ready to extract from EDF
    '''
    import pyedflib
    f = pyedflib.EdfReader(edf_file)
    placeholder_channels = [f.getLabel(i) for i in range(f.signals_in_file)]
    sampling_freq = f.getSampleFrequency(0)
    f.close()
    '''
    
    # For now, use placeholder sampling frequency
    sampling_freq = 2000
    
    # Create channel rows
    rows = []
    for channel_name in placeholder_channels:
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
    
    # Calculate bids_path: PRV-{patient_id}/primary/sub-PRV-{patient_id}/ses-visit-m{age}/eeg/
    bids_path = f"PRV-{patient_id}/primary/sub-PRV-{patient_id}/ses-visit-m{age}/eeg/"
    
    # Create custom filename: sub-PRV-<ptid>-<age>_task-rest_channels.tsv
    custom_filename = f"sub-PRV-{patient_id}-{age}_task-rest_channels.tsv"
    
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
