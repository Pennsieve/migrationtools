#!/usr/bin/env bash
set -euo pipefail

# --- Configuration ---
INPUT_CSV="migration_paths.csv"
EPS_TRACKER_FILE="epsnumber.csv"
TOOLS_DIR="$HOME/migrationtools"
LOG_FILE="$TOOLS_DIR/migration_log.txt"
MIGRATION_RESULTS_FILE="$TOOLS_DIR/migration_results.csv"

# --- Helper Functions ---
log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $message" | tee -a "$LOG_FILE"
}

record_result() {
    local folder="$1"
    local path="$2"
    local result="$3"
    echo "$folder,$path,$result" >> "$MIGRATION_RESULTS_FILE"
}

group_sessions_by_patient() {
    local -A patient_groups
    local -a ordered_patients
    
    # create tmp directory if it doesn't exist
    local tmp_dir="$HOME/tmp"
    mkdir -p "$tmp_dir"
    
    # create temporary file with full path
    local temp_groups="$tmp_dir/patient_groups_$$.txt"
    touch "$temp_groups"
    
    while IFS=',' read -r folder path; do
        [[ -z "$folder" || -z "$path" ]] && continue
        
        local patient_id
        patient_id=$(echo "$folder" | sed -E 's/(.+)-[0-9]+$/\1/')
        
        if [[ ! " ${ordered_patients[@]} " =~ " ${patient_id} " ]]; then
            ordered_patients+=("$patient_id")
        fi
        
        if [[ -n "${patient_groups[$patient_id]:-}" ]]; then
            patient_groups[$patient_id]+="###$folder###$path"
        else
            patient_groups[$patient_id]="$folder###$path"  
        fi
    done < "$INPUT_CSV"
    
    # clear and write to temp file
    : > "$temp_groups"
    for patient in "${ordered_patients[@]}"; do
        echo "$patient###${patient_groups[$patient]}" >> "$temp_groups"
    done

    # if the file exist and is not empty 
    if [[ -s "$temp_groups" ]]; then
        printf '%s\n' "$temp_groups"  
        return 0
    else
        log_message "❌ Error creating temporary groups file"
        return 1
    fi
}

# --- Validation ---
[ ! -f "$INPUT_CSV" ] && { echo "Missing $INPUT_CSV"; exit 1; }
[ ! -x "$TOOLS_DIR/edfandbid_creation.sh" ] && { echo "Missing $TOOLS_DIR/edfandbid_creation.sh"; exit 1; }

# Ensure results file exists 
if [ ! -f "$MIGRATION_RESULTS_FILE" ]; then
    echo "folder,migration_sheet,result" > "$MIGRATION_RESULTS_FILE"
fi

# --- Core Functions ---
download_from_aws() {
    local name_of_folder="$1"  # patient-session identifier 
    local migration_sheet_path="$2"  # path to patient-session folder in aws 
    local data_dir="$3"  # local /data directory 

    # download patient-session data from aws 
    log_message "Downloading from s3://org-ieeg-data/$migration_sheet_path"
    if ! aws s3 cp "s3://org-ieeg-data/$migration_sheet_path" "$data_dir" --recursive; then
        log_message "Download failed for '$name_of_folder'"
        record_result "$name_of_folder" "$migration_sheet_path" "DOWNLOAD_FAILED"
        return 1
    fi
    return 0
}

convert_to_bids() {
    local data_dir="$1"  # local /data directory
    local name_of_folder="$2"  # patient-session identifier
    local migration_sheet_path="$3"  # path to patient-session in aws 

    # runs edfandbid_creation.sh to convert into EDF data structure and BIDS folder structure
    log_message "Running edfandbid_creation.sh"
    cd "$TOOLS_DIR" || return 1
    ./edfandbid_creation.sh "$data_dir" "$TOOLS_DIR" ieeg | tee /tmp/conversion_log.txt

    if ! grep -q "Finished edf conversion and bids creation" /tmp/conversion_log.txt; then
        log_message "Conversion failed for '$name_of_folder'"
        record_result "$name_of_folder" "$migration_sheet_path" "FAILED_CONVERSION"
        return 1
    fi
    return 0
}

upload_to_pennsieve() {
    local eps_auto_number="$1"  # patient identifier 
    local eps_dir="$2"  # local patient folder 
    local name_of_folder="$3"  # patient-session identifier 
    local migration_sheet_path="$4"  # path to patient-session in aws

    # runs pennsieve dataset create and captures output into create_output
    log_message "Creating Pennsieve dataset: $eps_auto_number"
    local create_output
    create_output=$(pennsieve dataset create "$eps_auto_number" "Auto-migrated dataset for PREVeNT from ieeg.org" '["epilepsy", "epilepsy.science", "ieeg", "auto-migration"]')
    
    # extract dataset_node_id from create_output
    local dataset_node_id
    dataset_node_id=$(echo "$create_output" | grep 'NODE ID' | awk -F '|' '{gsub(/ /,"",$3); print $3}')

    if [ -z "$dataset_node_id" ]; then
        log_message "Failed to extract dataset NODE ID for '$name_of_folder'"
        record_result "$name_of_folder" "$migration_sheet_path" "FAILED_NODE_ID"
        return 1
    fi

    # runs pennsieve dataset use to set the dataset 
    pennsieve dataset use "$dataset_node_id"
    
    # runs pennsieve manifest create to create manifest for the local patient folder 
    local manifest_output manifest_id
    manifest_output=$(pennsieve manifest create "$eps_dir")
    manifest_id=$(echo "$manifest_output" | grep -oE 'Manifest ID: [^ ]+' | cut -d' ' -f3)
    
    if [ -z "$manifest_id" ]; then
        log_message "Manifest creation failed for '$name_of_folder'"
        record_result "$name_of_folder" "$migration_sheet_path" "MANIFEST_CREATION_FAILED"
        return 1
    fi

    # runs pennsieve upload manifest to upload the local patient folder with retries
    local max_retries=3
    for attempt in $(seq 1 $max_retries); do
        log_message "Attempt $attempt: Uploading manifest $manifest_id"
        if timeout 1800 pennsieve upload manifest "$manifest_id" </dev/null >>"$LOG_FILE" 2>&1; then
            record_result "$name_of_folder" "$migration_sheet_path" "$eps_auto_number"
            log_message "🏁 CONVERTED '$name_of_folder' TO '$eps_auto_number'"
            return 0
        fi
        log_message "Upload failed on attempt $attempt"
        sleep $((attempt * 10))
    done

    log_message "❌ Final upload failure for '$name_of_folder'"
    record_result "$name_of_folder" "$migration_sheet_path" "FAILED_UPLOAD"
    return 1
}

process_row() {
    local NAME_OF_FOLDER="$1"  # patient-session identifier
    local MIGRATION_SHEET_PATH="$2"  # path to patient-session folder in aws

    # clean input: remove the trailing carriage return
    NAME_OF_FOLDER="${NAME_OF_FOLDER%%[$'\r']}"
    MIGRATION_SHEET_PATH="${MIGRATION_SHEET_PATH%%[$'\r']}"

    DATA_DIR="$HOME/data/$NAME_OF_FOLDER"
    mkdir -p "$DATA_DIR"

    # Step 1: Download and convert to BIDS
    if ! download_from_aws "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH" "$DATA_DIR"; then
        return 1
    fi
    
    log_message "Download complete for '$NAME_OF_FOLDER'. Sleeping for 5 seconds"
    sleep 5

    # Get EPS number and directory
    if [ -f "$EPS_TRACKER_FILE" ]; then
        EPS_NUMBER=$(<"$EPS_TRACKER_FILE")
        if ! [[ "$EPS_NUMBER" =~ ^[0-9]+$ ]]; then
            log_message "EPS number not numeric or empty: $EPS_NUMBER"
            return 1
        fi
        ((EPS_NUMBER++))
        EPS_AUTO_NUMBER=$(printf "EPS%07d" "$EPS_NUMBER")
        EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"
    else
        log_message "WARNING: EPS_TRACKER_FILE not found or inaccessible"
        EPS_AUTO_NUMBER=$NAME_OF_FOLDER
        EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"
    fi

    # Step 2: Convert to BIDS format
    if ! convert_to_bids "$DATA_DIR" "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH"; then
        return 1
    fi

    log_message "Conversion successful for '$NAME_OF_FOLDER'. Sleeping for 5 seconds"
    sleep 5

    # Step 3: Merge multiple days if needed
    log_message "Running merge_days.py"
    if ! /usr/bin/python3 "$TOOLS_DIR/merge_days.py" "$HOME/data"; then
        log_message "❌ merge_days.py failed for '$NAME_OF_FOLDER'"
        record_result "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH" "FAILED_MERGE_DAYS"
        return 1
    fi

    # Step 4: Upload to Pennsieve
    if ! upload_to_pennsieve "$EPS_AUTO_NUMBER" "$EPS_DIR" "$NAME_OF_FOLDER" "$MIGRATION_SHEET_PATH"; then
        return 1
    fi
}

# --- Main Execution ---
main() {
    local total_patients=0
    local successful=0
    local failed=0

    log_message "🚀 Starting migration process"
    
    # group sessions by patient identifier and output a temporary txt file documentating the patient:patient_sessions,paths
    local groups_file
    groups_file=$(group_sessions_by_patient)
    total_patients=$(wc -l < "$groups_file")
    
    log_message "Found $total_patients patients to process"
    
    # read from group_file to obtain patient_id and sessions_data (comprised of patient_session identifier and path to aws)
    local current=0
    while IFS= read -r line || [ -n "$line" ]; do

        # ---- STEP 1: parse the group_file into patient_id, patient session id, and path_to_aws
        # split on the ### delimiter - sessions_data would be "###patient-session_identifer###path_to_aws###patient-session_identifer###path_to_aws###..."
        IFS='###' read -r patient_id sessions_data <<< "$line"
        # remove leading ## delimiter - session_data would be "patient-session_identifier###path_to_aws###patient-session_identifier###path_to_aws###..."
        sessions_data="${sessions_data##\#}"
        while [[ $sessions_data == \#* ]]; do sessions_data=${sessions_data#\#}; done
        # split on the ### delimiter - session_parts[0] would be "patient-session_identifier", then session_parts[1] be "path_to_aws", etc
        IFS='###' read -ra session_parts <<< "$sessions_data"

        # ----STEP 2: loop through the sessions for this patient to download from aws
        (( ++current ))   
        log_message "Processing patient $current of $total_patients: $patient_id"
        
        # to ensure the download of all sessions for this patient
        local success=true
        local all_data_dirs=()
        
        # firstly rocess session_parts in pairs (folder and path)
        local valid_parts=()
        for ((i=0; i<${#session_parts[@]}; i++)); do
            if [[ -n "${session_parts[i]}" ]]; then
                valid_parts+=("${session_parts[i]}")
            fi
        done
                
        # now process the valid parts in pairs
        for ((i=0; i<${#valid_parts[@]}; i+=2)); do
            folder="${valid_parts[i]}"
            path="${valid_parts[i+1]}"
            
            [[ -z "$folder" || -z "$path" ]] && continue
                        
            DATA_DIR="$HOME/data/$folder"
            mkdir -p "$DATA_DIR"
            
            # download the patient session data 
            if ! download_from_aws "$folder" "$path" "$DATA_DIR"; then
                success=false
                break
            fi
            all_data_dirs+=("$DATA_DIR")
        done
        
        # ---- STEP 3: only proceed if all downloads successful for merge_days.py to process later 
        if ! $success; then
            ((failed++))
            continue
        fi
        
        # get EPS number and DIR for the patient (for PREVeNT, wouldn't need to modify for EPS, would keep the original identifer)
        if [ -f "$EPS_TRACKER_FILE" ]; then
            EPS_NUMBER=$(<"$EPS_TRACKER_FILE")
            ((EPS_NUMBER++))
            EPS_AUTO_NUMBER=$(printf "EPS%07d" "$EPS_NUMBER")
            echo "$EPS_NUMBER" > "$EPS_TRACKER_FILE"
        else
            EPS_AUTO_NUMBER=$patient_id
        fi
        
        EPS_DIR="$HOME/data/$EPS_AUTO_NUMBER"
        
        # ---- STEP 4: convert all sessions to BIDS
        for dir in "${all_data_dirs[@]}"; do
            if ! convert_to_bids "$dir" "$(basename "$dir")" "$path"; then
                success=false
                break
            fi
        done

        # only proceed if all conversions successful
        if ! $success; then
            ((failed++))
            continue
        fi
        
        # ---- STEP 5: merge the sessions
        if ! /usr/bin/python3 "$TOOLS_DIR/merge_days.py" "$HOME/data"; then
            log_message "merge_days.py failed for patient '$patient_id'"
            ((failed++))
            continue
        fi
        
        # ---- STEP 6: upload merged result
        if ! upload_to_pennsieve "$EPS_AUTO_NUMBER" "$EPS_DIR" "$patient_id" "merged"; then
            ((failed++))
            continue
        fi
        
        ((successful++))
        log_message "Progress: $successful successful, $failed failed, $((total_patients - current)) remaining"
    done < "$groups_file"
    
    rm -f "$groups_file"  # clean up
    
    # summary
    log_message "🏁 Migration complete!"
    log_message "Final results:"
    log_message "✅ Successful: $successful"
    log_message "❌ Failed: $failed"
    log_message "📊 Total processed: $((successful + failed)) of $total_patients"
    
    [ "$failed" -eq 0 ]
}

# run main function
main
exit $?
