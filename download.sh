#!/bin/bash

set -euo pipefail

# --- Configuration ---
INPUT_CSV="migration_paths.csv"
EPS_TRACKER_FILE="epsnumber.csv"
TOOLS_DIR="$HOME/migrationtools"
LOG_FILE="$TOOLS_DIR/migration_log.txt"
MIGRATION_RESULTS_FILE="$TOOLS_DIR/migration_results.csv"

# --- Verify dependencies ---
[ ! -f "$INPUT_CSV" ] && { echo "Missing $INPUT_CSV"; exit 1; }
[ ! -f "$EPS_TRACKER_FILE" ] && { echo "Missing EPS number tracker: $EPS_TRACKER_FILE"; exit 1; }
[ ! -x "$TOOLS_DIR/edfandbid_creation.sh" ] && { echo "Missing edfandbid_creation.sh"; exit 1; }

# --- Ensure results file exists ---
if [ ! -f "$MIGRATION_RESULTS_FILE" ]; then
    echo "folder,migration_sheet,result" > "$MIGRATION_RESULTS_FILE"
fi

process_row() {
    local NAME_OF_FOLDER="$1"
    local MIGRATION_SHEET_PATH="$2"

    NAME_OF_FOLDER="${NAME_OF_FOLDER%%[$'\r']}"
    MIGRATION_SHEET_PATH="${MIGRATION_SHEET_PATH%%[$'\r']}"

    DATA_DIR="$HOME/data/$NAME_OF_FOLDER"
    mkdir -p "$DATA_DIR"

    echo "$DATA_DIR"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  Downloading from s3://org-ieeg-data/$MIGRATION_SHEET_PATH" | tee -a "$LOG_FILE"
    if ! aws s3 cp "s3://org-ieeg-data/$MIGRATION_SHEET_PATH" "$DATA_DIR" --recursive --quiet; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  Download failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,DOWNLOAD_FAILED" >> "$MIGRATION_RESULTS_FILE"
        return
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') Download complete for '$NAME_OF_FOLDER'. Sleeping for 5 seconds" | tee -a "$LOG_FILE"
    sleep 5

    EPS_NUMBER=$(<"$EPS_TRACKER_FILE")
    echo "Download EPS_NUMBER READ IN: $EPS_NUMBER"
    if ! [[ "$EPS_NUMBER" =~ ^[0-9]+$ ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  EPS number not numeric or empty: $EPS_NUMBER" | tee -a "$LOG_FILE"
        return
    fi

    ((EPS_NUMBER++))
    EPS_AUTO_NUMBER=$(printf "EPS%07d" "$EPS_NUMBER")
    EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"

    echo "$(date '+%Y-%m-%d %H:%M:%S') Step 3: Running edfandbid_creation.sh" | tee -a "$LOG_FILE"
    cd "$TOOLS_DIR" || { echo "$(date '+%Y-%m-%d %H:%M:%S') Could not enter $TOOLS_DIR" | tee -a "$LOG_FILE"; return; }
    ./edfandbid_creation.sh "$DATA_DIR" "$TOOLS_DIR" ieeg | tee /tmp/conversion_log.txt

    if ! grep -q "Finished edf conversion and bids creation" /tmp/conversion_log.txt; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  Conversion failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_CONVERSION" >> "$MIGRATION_RESULTS_FILE"
        return
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') Conversion successful for '$NAME_OF_FOLDER'. Sleeping for 5 seconds" | tee -a "$LOG_FILE"
    sleep 5

    return
}

# --- Main loop ---
 rm -rf ~/data/*
while IFS=',' read -r NAME_OF_FOLDER MIGRATION_SHEET_PATH; do
    [[ -z "$NAME_OF_FOLDER" || -z "$MIGRATION_SHEET_PATH" ]] && continue
    process_row "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH"
done < "$INPUT_CSV"
