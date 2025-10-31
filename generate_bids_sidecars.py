#!/usr/bin/env python3
"""
Generate BIDS sidecar files for the reorganized EEG data.
Discovers the BIDS structure and creates appropriate sidecars.
"""

# ==== Set up ==== #
# Basic setup
import os
import sys
from pathlib import Path
from collections import defaultdict

# Import the generator modules
from eeg_json_generator import handle_eeg_json
from channels_tsv_generator import handle_channels_tsv
from sessions_tsv_generator import handle_sessions_tsv

import sys, os, pprint
print("PYTHON EXE:", sys.executable)
print("PYTHONPATH env:", os.environ.get("PYTHONPATH"))
pprint.pp(sys.path[:10])


# ==== Helper Functions ==== #
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
