# Create a new environment for this project
```bash
conda create -n eeg_uploader python=3.11
```

# Activate it
```bash
conda activate eeg_uploader
```

# Install jsonschema and any other dependencies
```bash
conda install jsonschema
pip install -r requirements.txt
```



# EEG File Reorganizer

This tool reorganizes EDF and XML files from the input directory into a BIDS-like structure with automated sidecar file generation.

## Workflow Overview

The tool processes EDF and XML files with naming pattern `PRV-{site}-{patient_id}-{age}[A].{extension}` and creates a BIDS-compliant directory structure with associated metadata files.

## Input Structure

### Required Files

1. **EEG Data Files** (in `input/` directory):
   - Format: `PRV-{site}-{patient_id}-{age}[A].{extension}`
   - Example: `PRV-001-4ZHY-15-annotations.xml`, `PRV-001-4ZHY-15.edf`
   - Supported extensions: `.edf` (EEG data), `.xml` (annotations)
   - The `[A]` suffix is optional and indicates alternative recordings

2. **Patient Identifiers CSV** (`patient_identifiers.csv`):
   - Must contain columns: `patient_identifier`, `random_number`
   - Example:
     ```csv
     patient_identifier,random_number
     4ZHY,360
     7Y7J,-747
     ```
   - Only patients listed in this file will be processed

### Input Directory Example

```
input/
├── PRV-001-4ZHY-15.edf
├── PRV-001-4ZHY-15-annotations.xml
├── PRV-001-4ZHY-18.edf
├── PRV-001-4ZHY-18-annotations.xml
├── PRV-002-4ZHY-24.edf
└── PRV-002-4ZHY-24-annotations.xml
```

## How to Run

### Step 1: Install Dependencies

```bash
# Create conda environment
conda create -n eeg_uploader python=3.11
conda activate eeg_uploader
```

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install coreutils (macOS)
brew install coreutils

# Install jsonschema (choose one)
conda install -c conda-forge jsonschema
# OR
pip install jsonschema
```

### Step 2: Prepare Your Data

1. Place all EDF and XML files in the `input/` directory
2. Ensure `patient_identifiers.csv` is in the root directory with the correct patient IDs


### Step 3: Pennsieve Agent Running

```bash
# to start the agent
pennsieve agent 
# to check if you are in the correct workspace
pennsieve whoami
```

### Step 4: Run Complete Workflow

#### Option A: Run Everything at Once (Recommended)

Use the upload script to reorganize, generate sidecars, and upload to Pennsieve:

```bash
./upload.sh
```

This script will automatically:
1. Run BIDS reorganization (`reorganize_to_bids.py`)
2. Generate sidecar files (`generate_bids_sidecars.py`)
3. Upload all datasets to Pennsieve

Logs will be saved to `logs/upload_log.txt` and results to `logs/upload_results.csv`.

#### Option B: Run Steps Individually

If you only want to reorganize and generate sidecars without uploading:

**Reorganize Files:**
```bash
python reorganize_to_bids.py
```
This creates the directory structure and copies/renames files appropriately.

**Generate Sidecar Files:**
```bash
python generate_bids_sidecars.py
```
This generates:
- `*_eeg.json` files (EEG metadata)
- `*_channels.tsv` files (channel information)
- `*_sessions.tsv` files (session metadata)

The reorganized files with sidecars will be saved in the `output/` directory.

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
3. **Age Grouping**: Groups files by patient and age, creating sessions named `ses-visit{age}m`
4. **Structure Creation**: Creates the BIDS-like directory structure automatically
5. **File Copying**: Copies and renames files according to BIDS conventions
6. **Sidecar Generation**: Creates JSON and TSV metadata files for BIDS compliance

## Example Output Structure

For patient `4ZHY` with ages 15, 18, and 24:

```
output/PRV-4ZHY/primary/sub-4ZHY/
├── sub-4ZHY_sessions.tsv
├── ses-visit15m/eeg/
│   ├── sub-4ZHY_ses-visit15m_task-prv.edf
│   ├── sub-4ZHY_ses-visit15m_task-prv.xml
│   ├── sub-4ZHY_ses-visit15m_task-prv_eeg.json
│   └── sub-4ZHY_ses-visit15m_task-prv_channels.tsv
├── ses-visit18m/eeg/
│   ├── sub-4ZHY_ses-visit18m_task-prv.edf
│   ├── sub-4ZHY_ses-visit18m_task-prv.xml
│   ├── sub-4ZHY_ses-visit18m_task-prv_eeg.json
│   └── sub-4ZHY_ses-visit18m_task-prv_channels.tsv
└── ses-visit24m/eeg/
    ├── sub-4ZHY_ses-visit24m_task-prv.edf
    ├── sub-4ZHY_ses-visit24m_task-prv.xml
    ├── sub-4ZHY_ses-visit24m_task-prv_eeg.json
    └── sub-4ZHY_ses-visit24m_task-prv_channels.tsv
```

### Generated Files

- **EDF files**: Raw EEG data
- **XML files**: Annotation data
- **_eeg.json**: BIDS-compliant EEG metadata (sampling rate, channels, manufacturer, etc.)
- **_channels.tsv**: Channel-specific information (names, types, units, sampling frequency)
- **_sessions.tsv**: Session-level metadata across all visits for a patient
