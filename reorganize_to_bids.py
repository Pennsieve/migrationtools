#!/usr/bin/env python3
"""
Script to reorganize EDF and XML files into BIDS-like structure.
"""

import os
import shutil
import pandas as pd
import re
from pathlib import Path
from collections import defaultdict

def parse_filename(filename):
    """
    Parse filename to extract site, patient_id, and age.
    Expected format: PRV-{site}-{patient_id}-{age}[A].{extension}
    """
    # Remove the file extension first
    name_without_ext = os.path.splitext(filename)[0]
    
    # Remove '-annotations' suffix if present
    if name_without_ext.endswith('-annotations'):
        name_without_ext = name_without_ext[:-12]
    
    # Parse the pattern PRV-{site}-{patient_id}-{age}[A]
    pattern = r'PRV-(\d+)-([A-Z0-9]+)-(\d+)([A-Z]?)'
    match = re.match(pattern, name_without_ext)
    
    if match:
        site = match.group(1)
        patient_id = match.group(2)
        age = int(match.group(3))
        suffix = match.group(4)  # Optional A suffix
        return site, patient_id, age, suffix
    else:
        raise ValueError(f"Could not parse filename: {filename}")

def get_files_by_patient(input_dir, patient_identifiers):
    """
    Group files by patient identifier.
    Return a list of:
        filename (e.g. PRV-001-4ZHY-15-annotations.xml), 
        site (e.g. 001),
        age (e.g. 15),
        suffix (e.g. A or '' in the case there are PRV-001-4ZHY-15A),
        extension (e.g. .xml or .edf)
    for each patient id (list called files_by_patient).
    """
    files_by_patient = defaultdict(list)
    
    for filename in os.listdir(input_dir):
        if filename.endswith(('.edf', '.xml')):
            try:
                site, patient_id, age, suffix = parse_filename(filename)
                
                # Check if this patient_id is in our list
                if patient_id in patient_identifiers:
                    files_by_patient[patient_id].append({
                        'filename': filename,
                        'site': site,
                        'age': age,
                        'suffix': suffix,
                        'extension': os.path.splitext(filename)[1]
                    })
            except ValueError as e:
                print(f"Warning: {e}")
    
    return files_by_patient

def create_bids_structure(files_by_patient, input_dir, output_dir):
    """
    Create BIDS-like structure and copy files.
    """

    # loop through each patient
    for patient_id, files in files_by_patient.items():
        print(f"\nProcessing patient: {patient_id}")
        
        # Group files by age
        files_by_age = defaultdict(list)
        for file_info in files:
            files_by_age[file_info['age']].append(file_info) # get age from files_by_patient created by get_files_by_patient
        
        ages = sorted(files_by_age.keys())
        print(f"  Ages found: {ages}")
        
        # Get site from first file; create dataset name PRV-{patient_id}
        site = files[0]['site']
        dataset_name = f"PRV-{patient_id}"
        
        # Create subject  structure
        base_path = Path(output_dir) / dataset_name / "primary" / f"sub-{dataset_name}" # e.g. output/PRV-4ZHY/primary/sub-PRV-4ZHY
        
        for age in ages:
            # Create session name with visit-m<age> format
            session = f"ses-visit-m{age}"
            
            # Create session directory
            session_path = base_path / session / "eeg" # e.g. output/PRV-4ZHY/primary/sub-PRV-4ZHY/ses-visit-m15/eeg
            session_path.mkdir(parents=True, exist_ok=True)
                        
            # Process files for this age
            for file_info in files_by_age[age]: # get files for this age
                src_file = Path(input_dir) / file_info['filename']
                
                # Create new filename
                if file_info['extension'] == '.xml':
                    new_filename = f"sub-{dataset_name}-{age}.xml" #e.g. sub-PRV-4ZHY-15.xml
                else:
                    new_filename = f"sub-{dataset_name}-{age}.edf"
                
                dst_file = session_path / new_filename
                                
                # copy files from src to dst with new filename
                shutil.copy2(src_file, dst_file)

def main():

    # Paths
    script_dir = Path(__file__).parent
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    patient_csv = script_dir / "patient_identifiers.csv"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Read patient identifiers
    df = pd.read_csv(patient_csv)
    patient_identifiers = set(df['patient_identifier'].astype(str))
    
    print(f"Found {len(patient_identifiers)} patient identifiers: {sorted(patient_identifiers)}")
    
    # Get files grouped by patient
    files_by_patient = get_files_by_patient(input_dir, patient_identifiers)
    
    print(f"Found files for {len(files_by_patient)} patients")
    
    # Create BIDS structure
    create_bids_structure(files_by_patient, input_dir, output_dir)
    

if __name__ == "__main__":
    main()