# PREVeNT EEG Data Uploader

De-identifies, BIDS-formats, and uploads EEG data to Pennsieve.

## Setup

```bash
# Create and activate conda environment
conda create -n prevent_upload python=3.11
conda activate prevent_upload

# Install dependencies
pip install -r requirements.txt
pip install pyedflib
conda install -c conda-forge jsonschema

# macOS only: install coreutils
brew install coreutils
```

## Prepare Data

1. Place all original EDF and XML files in `/origin/`
2. Place `metadata.csv` or `metadata.xlsx` in `/origin/metadata/`
3. Place `patient_identifiers.csv` in the root directory

## Verify Pennsieve Agent

```bash
pennsieve agent
pennsieve whoami  # Confirm correct workspace
```

## Run

```bash
# Step 1 (Optioinal): Convert the metadata.xlsx to csv 
bash process_eeg_metadata.py

# Step 2: De-identify patient data
./main.sh

# Step 3: BIDS-format and upload
./upload.sh
```

Logs are saved to `logs/upload_log.txt` and results to `logs/upload_results.csv`.


