#!/usr/bin/env python3
"""
Script to reorganize EDF and XML files into BIDS-like structure.
"""

import os
import shutil
import pandas as pd
import re
import sys
from pathlib import Path
from collections import defaultdict


def load_metadata(metadata_path):
    """
    Load metadata.csv, skipping the first row and using the second row as header.
    Parse 'Filename (Final List)' to extract age and add as new column.
    Returns a DataFrame with PID1, Filename (Final List Age), and session columns.
    """
    # Read CSV, skip first row, use second row as header
    df = pd.read_csv(metadata_path, skiprows=1)

    # Parse age from 'Filename (Final List)' column (format: PRV-<site>-<patient_id>-<age>)
    def extract_age_from_filename(filename):
        if pd.isna(filename):
            return None
        # Pattern: PRV-<site>-<patient_id>-<age>
        pattern = r'PRV-\d+-[A-Z0-9]+-(\d+)'
        match = re.match(pattern, str(filename))
        if match:
            return int(match.group(1))
        return None

    df['Filename (Final List Age)'] = df['Filename (Final List)'].apply(extract_age_from_filename)

    return df


def get_session_from_metadata(metadata_df, patient_id, age):
    """
    Look up the session name from metadata for a given patient_id and age.
    Returns the session value or None if no match found.
    """
    # Match on PID1 and Filename (Final List Age)
    match = metadata_df[
        (metadata_df['PID1'] == patient_id) &
        (metadata_df['Filename (Final List Age)'] == age)
    ]

    if match.empty:
        return None

    return match.iloc[0]['session']


def parse_filename(filename):
    """
    Parse filename to extract patient_id and age.
    Expected format: PRV-{patient_id}-{age}[A].{extension}
    """
    # Remove the file extension first
    name_without_ext = os.path.splitext(filename)[0]
    
    # Remove '-annotations' suffix if present
    if name_without_ext.endswith('-annotations'):
        name_without_ext = name_without_ext[:-12]
    
    # Parse the pattern PRV-{site}-{patient_id}-{age}[A]
    # pattern = r'PRV-(\d+)-([A-Z0-9]+)-(\d+)([A-Z]?)'
    # pattern = r'PRV-([A-Z0-9]+)-(\d+)([A-Z]?)'
    pattern = r'^PRV-([A-Z0-9]+)-(\d+)([A-Z]?)+(?:-[^-]+)?'
    match = re.match(pattern, name_without_ext)
    
    if match:
        # site = match.group(1)
        patient_id = match.group(1)
        age = int(match.group(2))
        suffix = match.group(3)  # Optional A suffix
        # return site, patient_id, age, suffix
        return patient_id, age, suffix
    else:
        raise ValueError(f"Could not parse filename: {filename}")

def get_files_by_patient(input_dir, patient_identifiers):
    """
    Group files by patient identifier.
    Return a list of:
        filename (e.g. PRV-4ZHY-15-annotations.xml), 
        age (e.g. 15),
        suffix (e.g. A or '' in the case there are PRV-001-4ZHY-15A),
        extension (e.g. .xml or .edf)
    for each patient id (list called files_by_patient).
    """
    files_by_patient = defaultdict(list)
    
    for filename in os.listdir(input_dir):
        if filename.endswith(('.edf', '.xml')):
            try:
                # site, patient_id, age, suffix = parse_filename(filename)
                patient_id, age, suffix = parse_filename(filename)
                
                # Check if this patient_id is in our list
                if patient_id in patient_identifiers:
                    files_by_patient[patient_id].append({
                        'filename': filename,
                        # 'site': site,
                        'age': age,
                        'suffix': suffix,
                        'extension': os.path.splitext(filename)[1]
                    })
            except ValueError as e:
                print(f"Warning: {e}")
    
    return files_by_patient

def create_bids_structure(files_by_patient, input_dir, output_dir, metadata_df):
    """
    Create BIDS-like structure and copy files.
    Uses metadata_df to look up session names.
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

        # Create dataset name in format "PREVeNT Trial <patient-id>"
        dataset_name = f"PREVeNT Trial {patient_id}"

        # Create subject structure (base_path remains the same)
        base_path = Path(output_dir) / dataset_name / "primary" / f"sub-{patient_id}" # e.g. output/PRV-4ZHY/primary/sub-4ZHY

        for age in ages:
            # Look up session from metadata
            session = get_session_from_metadata(metadata_df, patient_id, age)

            if session is None:
                print(f"[ERROR]: No matching metadata found for patient_id={patient_id}, age={age}")
                print("Exiting due to missing metadata match.")
                sys.exit(1)

            # Create session directory
            session_path = base_path / session / "eeg" # e.g. output/PRV-4ZHY/primary/sub-4ZHY/ses-visit15m/eeg
            session_path.mkdir(parents=True, exist_ok=True)

            # Process files for this age
            for file_info in files_by_age[age]: # get files for this age
                src_file = Path(input_dir) / file_info['filename']

                # Create new filename using session from metadata
                # Format: sub-{patient_id}_{session}_task-prv.{extension}
                ext = file_info['extension']  # includes the dot, e.g. '.xml' or '.edf'
                new_filename = f"sub-{patient_id}_{session}_task-prv{ext}"

                dst_file = session_path / new_filename

                # copy files from src to dst with new filename
                shutil.copy2(src_file, dst_file)

def main():

    # Paths
    script_dir = Path(__file__).parent
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    patient_csv = script_dir / "patient_identifiers.csv"
    metadata_csv = script_dir / "origin" / "metadata" / "metadata.csv"

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Load metadata
    print(f"Loading metadata from: {metadata_csv}")
    metadata_df = load_metadata(metadata_csv)
    print(f"Loaded {len(metadata_df)} metadata rows")

    # Read patient identifiers
    df = pd.read_csv(patient_csv)
    patient_identifiers = set(df['patient_identifier'].astype(str))

    print(f"Found {len(patient_identifiers)} patient identifiers: {sorted(patient_identifiers)}")

    # Get files grouped by patient
    files_by_patient = get_files_by_patient(input_dir, patient_identifiers)

    print(f"Found files for {len(files_by_patient)} patients")

    # Create BIDS structure
    create_bids_structure(files_by_patient, input_dir, output_dir, metadata_df)
    

if __name__ == "__main__":
    main()