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

    EPS_NUMBER=$(<"$EPS_TRACKER_FILE")
    echo "READ EPS NUMBER $EPS_NUMBER for upload"
    if ! [[ "$EPS_NUMBER" =~ ^[0-9]+$ ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  EPS number not numeric or empty: $EPS_NUMBER" | tee -a "$LOG_FILE"
        return
    fi

    ((EPS_NUMBER++))
    EPS_AUTO_NUMBER=$(printf "EPS%07d" "$EPS_NUMBER")
    EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"

    echo "$(date '+%Y-%m-%d %H:%M:%S') Creating Pennsieve dataset: $EPS_AUTO_NUMBER" | tee -a "$LOG_FILE"
    CREATE_OUTPUT=$(pennsieve dataset create "$EPS_AUTO_NUMBER" "Auto-migrated dataset from ieeg.org" '["epilepsy", "epilepsy.science", "ieeg", "auto-migration"]')
    echo "$CREATE_OUTPUT"

    DATASET_NODE_ID=$(echo "$CREATE_OUTPUT" | grep 'NODE ID' | awk -F '|' '{gsub(/ /,"",$3); print $3}')
    if [ -z "$DATASET_NODE_ID" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ Failed to extract dataset NODE ID for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_NODE_ID" >> "$MIGRATION_RESULTS_FILE"
        return
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') Created dataset with NODE ID: $DATASET_NODE_ID. Sleep for 2.5 seconds" | tee -a "$LOG_FILE"
    sleep 2.5
    pennsieve dataset use "$DATASET_NODE_ID"

    echo "EPSDIR: $EPS_DIR"

    MANIFEST_OUTPUT=$(pennsieve manifest create "$EPS_DIR")
    MANIFEST_ID=$(echo "$MANIFEST_OUTPUT" | grep -oE 'Manifest ID: [^ ]+' | cut -d' ' -f3)
    if [ -z "$MANIFEST_ID" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ Manifest creation failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,MANIFEST_CREATION_FAILED" >> "$MIGRATION_RESULTS_FILE"
        return
    fi

    MAX_RETRIES=3
    for attempt in $(seq 1 $MAX_RETRIES); do
        echo "$(date '+%Y-%m-%d %H:%M:%S') Attempt $attempt: Uploading manifest $MANIFEST_ID" | tee -a "$LOG_FILE"
        if timeout 1800 pennsieve upload manifest "$MANIFEST_ID" </dev/null >>"$LOG_FILE" 2>&1; then
            echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,$EPS_AUTO_NUMBER" >> "$MIGRATION_RESULTS_FILE"
            echo "$EPS_NUMBER" > "$EPS_TRACKER_FILE"
            echo "$(date '+%Y-%m-%d %H:%M:%S') 🏁 CONVERTED '$NAME_OF_FOLDER' TO '$EPS_AUTO_NUMBER'" | tee -a "$LOG_FILE"
            return
        fi
        echo "$(date '+%Y-%m-%d %H:%M:%S') Upload failed on attempt $attempt" | tee -a "$LOG_FILE"
        sleep $((attempt * 30))
    done

    echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ Final upload failure for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
    echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_UPLOAD" >> "$MIGRATION_RESULTS_FILE"
    return
}

read -r NAME_OF_FOLDER MIGRATION_SHEET_PATH < "$INPUT_CSV"
process_row "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH"

