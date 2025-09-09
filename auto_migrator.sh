#!/bin/bash
set -euo pipefail



## SETUP 
# Configuration 
INPUT_CSV="migration_paths.csv"
EPS_TRACKER_FILE="epsnumber.csv"
TOOLS_DIR="$HOME/migrationtools"
LOG_FILE="$TOOLS_DIR/migration_log.txt"
MIGRATION_RESULTS_FILE="$TOOLS_DIR/migration_results.csv"

# Verify dependencies 
[ ! -f "$INPUT_CSV" ] && { echo "Missing $INPUT_CSV"; exit 1; }
[ ! -x "$TOOLS_DIR/edfandbid_creation.sh" ] && { echo "Missing $TOOLS_DIR/edfandbid_creation.sh"; exit 1; }

# Ensure results file exists 
if [ ! -f "$MIGRATION_RESULTS_FILE" ]; then
    echo "folder,migration_sheet,result" > "$MIGRATION_RESULTS_FILE"
fi



## FUNCTION
process_row() {
    local NAME_OF_FOLDER="$1"
    local MIGRATION_SHEET_PATH="$2"

    NAME_OF_FOLDER="${NAME_OF_FOLDER%%[$'\r']}"
    MIGRATION_SHEET_PATH="${MIGRATION_SHEET_PATH%%[$'\r']}"

    DATA_DIR="$HOME/data/$NAME_OF_FOLDER"
    mkdir -p "$DATA_DIR"

    # downloading data from aws 
    echo "$DATA_DIR"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  Downloading from s3://org-ieeg-data/$MIGRATION_SHEET_PATH" | tee -a "$LOG_FILE"
    if ! aws s3 cp "s3://org-ieeg-data/$MIGRATION_SHEET_PATH" "$DATA_DIR" --recursive; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  Download failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,DOWNLOAD_FAILED" >> "$MIGRATION_RESULTS_FILE"
        return
    fi

    # DEBUG: After AWS download:
    echo "=== Folder structure after AWS download ===" | tee -a "$LOG_FILE"
    tree "$DATA_DIR" | tee -a "$LOG_FILE"
    echo "=========================================" | tee -a "$LOG_FILE"
    # DEBUG END

    echo "$(date '+%Y-%m-%d %H:%M:%S') Download complete for '$NAME_OF_FOLDER'. Sleeping for 5 seconds" | tee -a "$LOG_FILE"
    sleep 5

    # DEBUG: check if EPS_TRACKER_FILE exists
    if [ -f "$EPS_TRACKER_FILE" ]; then
        # check if EPS_NUMBER is valid
        EPS_NUMBER=$(<"$EPS_TRACKER_FILE")
        if ! [[ "$EPS_NUMBER" =~ ^[0-9]+$ ]]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S')  EPS number not numeric or empty: $EPS_NUMBER" | tee -a "$LOG_FILE"
            return
        fi
        # edit EPS_NUMBER and set up EPS_DIR 
        ((EPS_NUMBER++))
        EPS_AUTO_NUMBER=$(printf "EPS%07d" "$EPS_NUMBER")
        EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"
    else
        echo "WARNING: EPS_TRACKER_FILE not found or inaccessible" | tee -a "$LOG_FILE"
        EPS_AUTO_NUMBER=$NAME_OF_FOLDER
        EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"
    fi
    # DEBUG END

    # Run edfandbid_creation.sh
    echo "$(date '+%Y-%m-%d %H:%M:%S') Running edfandbid_creation.sh" | tee -a "$LOG_FILE"
    cd "$TOOLS_DIR" || { echo "$(date '+%Y-%m-%d %H:%M:%S') Could not enter $TOOLS_DIR" | tee -a "$LOG_FILE"; return; }
    ./edfandbid_creation.sh "$DATA_DIR" "$TOOLS_DIR" ieeg | tee /tmp/conversion_log.txt

    if ! grep -q "Finished edf conversion and bids creation" /tmp/conversion_log.txt; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  Conversion failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_CONVERSION" >> "$MIGRATION_RESULTS_FILE"
        return
    fi    

    # DEBUG: After edfandbid_creation.sh:
    echo "=== Folder structure after BIDS conversion ===" | tee -a "$LOG_FILE"
    tree "$EPS_DIR" | tee -a "$LOG_FILE"
    echo "=============================================" | tee -a "$LOG_FILE"
    # DEBUG END

    echo "$(date '+%Y-%m-%d %H:%M:%S') Conversion successful for '$NAME_OF_FOLDER'. Sleeping for 5 seconds" | tee -a "$LOG_FILE"
    sleep 5

    # Run merge_days.py to merge patients' data taken on different days
    echo "$(date '+%Y-%m-%d %H:%M:%S') Running merge_days.py" | tee -a "$LOG_FILE"
    /usr/bin/python3 "$TOOLS_DIR/merge_days.py" "$HOME/data"
    if [ $? -ne 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ merge_days.py failed for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
        echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_MERGE_DAYS" >> "$MIGRATION_RESULTS_FILE"
        return
    fi


   # NOTE: code to upload to pennsieve 
   echo "$(date '+%Y-%m-%d %H:%M:%S') Creating Pennsieve dataset: $EPS_AUTO_NUMBER" | tee -a "$LOG_FILE"
    CREATE_OUTPUT=$(pennsieve dataset create "$EPS_AUTO_NUMBER" "Auto-migrated dataset for PREVeNT from ieeg.org" '["epilepsy", "epilepsy.science", "ieeg", "auto-migration"]')
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
           echo "$(date '+%Y-%m-%d %H:%M:%S') 🏁 CONVERTED '$NAME_OF_FOLDER' TO '$EPS_AUTO_NUMBER'" | tee -a "$LOG_FILE"
           return
       fi
       echo "$(date '+%Y-%m-%d %H:%M:%S') Upload failed on attempt $attempt" | tee -a "$LOG_FILE"
       sleep $((attempt * 10))
   done
    return

    echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ Final upload failure for '$NAME_OF_FOLDER'" | tee -a "$LOG_FILE"
    echo "$NAME_OF_FOLDER,$MIGRATION_SHEET_PATH,FAILED_UPLOAD" >> "$MIGRATION_RESULTS_FILE"
    return
}

# --- Main loop ---
while IFS=',' read -r NAME_OF_FOLDER MIGRATION_SHEET_PATH; do
    [[ -z "$NAME_OF_FOLDER" || -z "$MIGRATION_SHEET_PATH" ]] && continue
    process_row "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH"
done < "$INPUT_CSV"
