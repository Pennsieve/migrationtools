# EEG File Reorganizer

This tool reorganizes EDF and XML files from the input directory into a BIDS-like structure.

## Workflow Overview

The script takes EDF and XML files with naming pattern `PRV-{site}-{patient_id}-{age}[A].{extension}` and reorganizes them into:

```
output/
├── PRV-{patient_id}/
│   └── primary/
│       └── sub-PRV-{patient_id}/
│           ├── ses-baseline-{min_age}/
│           │   └── eeg/
│           │       ├── sub-PRV-{patient_id}-{min_age}.edf
│           │       └── sub-PRV-{patient_id}-{min_age}.xml
│           ├── ses-followup-{age}/
│           │   └── eeg/
│           │       ├── sub-PRV-{patient_id}-{age}.edf
│           │       └── sub-PRV-{patient_id}-{age}.xml
│           └── ...
```

## Usage

1. Install dependencies:
```bash
pip install -r requirements.txt
```
Also need to make sure you have coreutils (timeout) installed locally.

2. Ensure your files are in the `input/` directory and patient identifiers are in `patient_identifiers.csv`

3. Run the reorganization script:
```bash
python reorganize_to_bids.py
```

The reorganized files will be saved in the `output/` directory.

## File Structure

- `input/`: Contains the original EDF and XML files
- `patient_identifiers.csv`: CSV file with patient identifiers (columns: patient_identifier, random_number)
- `reorganize_to_bids.py`: Main reorganization script
- `run_example.py`: Example script demonstrating usage
- `requirements.txt`: Python dependencies
- `output/`: Generated BIDS-like structure (created after running the script)

## How It Works

1. **File Parsing**: The script parses filenames with pattern `PRV-{site}-{patient_id}-{age}[A].{extension}`
2. **Patient Matching**: Only processes files for patient IDs listed in `patient_identifiers.csv`
3. **Age Grouping**: Groups files by patient and age, with the lowest age designated as "baseline"
4. **Structure Creation**: Creates the BIDS-like directory structure automatically
5. **File Copying**: Copies and renames files according to BIDS conventions

## Example Output Structure

For patient `4ZHY` with ages 15, 18, and 24:

```
output/PRV-4ZHY/primary/sub-PRV-4ZHY/
├── ses-baseline-15/eeg/
│   ├── sub-PRV-4ZHY-15.edf
│   └── sub-PRV-4ZHY-15.xml
├── ses-followup-18/eeg/
│   ├── sub-PRV-4ZHY-18.edf
│   └── sub-PRV-4ZHY-18.xml
└── ses-followup-24/eeg/
    ├── sub-PRV-4ZHY-24.edf
    └── sub-PRV-4ZHY-24.xml
```

## Features

- **Simple and straightforward**: Single Python script with minimal dependencies
- **Automatic baseline detection**: Smallest age becomes baseline session
- **Robust file parsing**: Handles optional suffixes (like 'A') and annotation files
- **Safe operation**: Creates new directory structure without modifying original files
- **Progress reporting**: Shows which files are being processed and where they're placed

