#!/usr/bin/env bash
set -euo pipefail

# --- Configuration ---
INPUT_CSV="migration_paths.csv"
#EPS_TRACKER_FILE="epsnumber.csv"
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

reorganize_folder_structure() {
    local patient_id="$1"        # e.g., PRV-001-13UL (after merge_days.py)
    local patient_dir="$2"       # e.g., $HOME/data/PRV-001-13UL
    
    log_message "Reorganizing folder structure for Pennsieve upload"
    
    # Extract the subject ID without site code: PRV-001-13UL -> PRV-13UL
    # Split by hyphens and reconstruct without the middle site code
    local parts
    IFS='-' read -ra parts <<< "$patient_id"
    
    # parts[0] = PRV, parts[1] = 001, parts[2] = 13UL
    # We want PRV-13UL (skip the site code)
    local subject_id="${parts[0]}-${parts[2]}"  # PRV-13UL
    
    log_message "Converting $patient_id to subject $subject_id"
    
    # Create temporary directory for reorganization
    local temp_dir="${patient_dir}_pennsieve"
    rm -rf "$temp_dir"  # Clean if exists
    mkdir -p "$temp_dir"
    
    # Move BIDS metadata files to root level
    if [ -f "$patient_dir/primary/dataset_description.json" ]; then
        cp "$patient_dir/primary/dataset_description.json" "$temp_dir/" || log_message "⚠️  No dataset_description.json found"
    fi
    if [ -f "$patient_dir/primary/participants.json" ]; then
        cp "$patient_dir/primary/participants.json" "$temp_dir/" || log_message "⚠️  No participants.json found"
    fi
    if [ -f "$patient_dir/primary/participants.tsv" ] || [ -f "$patient_dir/primary/partcipants.tsv" ]; then
        cp "$patient_dir/primary/participants.tsv" "$temp_dir/" 2>/dev/null || \
        cp "$patient_dir/primary/partcipants.tsv" "$temp_dir/participants.tsv" 2>/dev/null || \
        log_message "⚠️  No participants.tsv found"
    fi
    
    # Find the ieeg base directory with session folders
    local ieeg_base="$patient_dir/primary/sub-${patient_id}/ses-postimplant/ieeg"
    
    # Debug: Log what we're looking for
    log_message "Looking for ieeg directory at: $ieeg_base"
    log_message "Contents of $patient_dir:"
    ls -la "$patient_dir" >> "$LOG_FILE" 2>&1 || true
    log_message "Contents of $patient_dir/primary:"
    ls -la "$patient_dir/primary" >> "$LOG_FILE" 2>&1 || true
    
    if [ ! -d "$ieeg_base" ]; then
        log_message "❌ No ieeg directory found at $ieeg_base"
        log_message "Checking what actually exists in primary folder:"
        find "$patient_dir/primary" -type d -maxdepth 3 >> "$LOG_FILE" 2>&1 || true
        return 1
    fi
    
    log_message "Processing session folders in $ieeg_base"
    
    # Debug: Show what session folders exist
    log_message "Looking for ses-* folders in $ieeg_base:"
    ls -la "$ieeg_base" >> "$LOG_FILE" 2>&1 || true
    
    # Process each session folder (ses-03, ses-04, ses-06, etc.)
    local session_count=0
    for session_dir in "$ieeg_base"/ses-*/; do
        log_message "Checking session_dir: $session_dir"
        if [ ! -d "$session_dir" ]; then
            log_message "  Not a directory, skipping"
            continue
        fi
        
        # Extract session number: ses-03 -> 03, ses-04 -> 04, etc.
        local session_name=$(basename "$session_dir")
        local session_num="${session_name#ses-}"  # Remove 'ses-' prefix
        
        # Create full session folder name: PRV-13UL-03
        local full_session_name="${subject_id}-${session_num}"
        
        log_message "  Creating session folder: $full_session_name"
        
        # Create session folder structure
        # Create EEG primary and derivatives folders
        local session_folder="$temp_dir/$full_session_name"
        mkdir -p "$session_folder/eeg/primary"
        mkdir -p "$session_folder/eeg/derivatives"
        
        # Move all files from session directory to eeg/primary
        if [ "$(ls -A "$session_dir")" ]; then
            mv "$session_dir"/* "$session_folder/eeg/primary/" 2>/dev/null || \
                log_message "⚠️  No files to move from $session_name"
        fi
        
        # Make visit_phenotype folder and create visit_description.json within
        mkdir -p "$session_folder/visit_phenotype"
        cat > "$session_folder/visit_phenotype/visit_description.json" <<EOF
{
  "SessionID": "$full_session_name",
  "SubjectID": "$subject_id",
  "SessionNumber": "$session_num",
  "DataType": "eeg"
}
EOF
        
        ((session_count++))
    done
    
    # Copy derivative files to each session folder
    if [ -d "$patient_dir/derivative" ] && [ "$(ls -A "$patient_dir/derivative" 2>/dev/null)" ]; then
        log_message "Copying derivative files to session folders"
        for session_folder in "$temp_dir"/*-*/; do
            if [ -d "$session_folder/eeg/derivatives" ]; then
                cp -r "$patient_dir/derivative"/* "$session_folder/eeg/derivatives/" 2>/dev/null || true
            fi
        done
    fi
    
    log_message "✅ Created $session_count session folders"
    
    # Replace old directory with new structure
    # Rename to final subject ID (PRV-13UL)
    local final_dir="$HOME/data/$subject_id"
    rm -rf "$final_dir"  # Remove if exists
    mv "$temp_dir" "$final_dir"
    rm -rf "$patient_dir"  # Clean up old structure
    
    log_message "✅ Folder reorganization complete: $final_dir"
    
    # Return the new directory path
    echo "$final_dir"
    return 0
}

upload_to_pennsieve() {
    local PATIENT_ID="$1"  # patient identifier 
    local LOCAL_DATA_DIR="$2"  # local patient folder 
    local name_of_folder="$3"  # patient-session identifier 
    local migration_sheet_path="$4"  # path to patient-session in aws

    # runs pennsieve dataset create and captures output into create_output
    log_message "Creating Pennsieve dataset: $PATIENT_ID"
    local create_output
    create_output=$(pennsieve dataset create "$PATIENT_ID" "Auto-migrated dataset for PREVeNT from ieeg.org" '["epilepsy", "epilepsy.science", "ieeg", "auto-migration"]')
    
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
    manifest_output=$(pennsieve manifest create "$LOCAL_DATA_DIR")
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
            record_result "$name_of_folder" "$migration_sheet_path" "$PATIENT_ID"
            log_message "🏁 CONVERTED '$name_of_folder' TO '$PATIENT_ID'"
            return 0
        fi
        log_message "Upload failed on attempt $attempt"
        sleep $((attempt * 10))
    done

    log_message "❌ Final upload failure for '$name_of_folder'"
    record_result "$name_of_folder" "$migration_sheet_path" "FAILED_UPLOAD"
    return 1
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

        # ==== STEP 1: parse the group_file into patient_id, patient session id, and path_to_aws
        # split on the ### delimiter - sessions_data would be "###patient-session_identifer###path_to_aws###patient-session_identifer###path_to_aws###..."
        IFS='###' read -r patient_id sessions_data <<< "$line"
        # remove leading ## delimiter - session_data would be "patient-session_identifier###path_to_aws###patient-session_identifier###path_to_aws###..."
        sessions_data="${sessions_data##\#}"
        while [[ $sessions_data == \#* ]]; do sessions_data=${sessions_data#\#}; done
        # split on the ### delimiter - session_parts[0] would be "patient-session_identifier", then session_parts[1] be "path_to_aws", etc
        IFS='###' read -ra session_parts <<< "$sessions_data"

        # ==== STEP 2: loop through the sessions for this patient to download from aws
        (( ++current ))   
        log_message "Processing patient $current of $total_patients: $patient_id"
        
        # to ensure the download of all sessions for this patient
        local success=true
        local all_data_dirs=()
        
        # firstly process session_parts in pairs (folder and path)
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
        
        # ==== STEP 3: only proceed if all downloads successful for merge_days.py to process later 
        if ! $success; then
            ((failed++))
            continue
        fi
        
        # ==== STEP 4: convert all sessions to BIDS
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
        
        # ==== STEP 5: merge the sessions
        # merge_days.py will create a merged folder named after the patient_id (e.g., PRV-001-13UL)
        if ! /usr/bin/python3 "$TOOLS_DIR/merge_days.py" "$HOME/data"; then
            log_message "merge_days.py failed for patient '$patient_id'"
            ((failed++))
            continue
        fi
        
        # After merge_days.py, the merged folder should exist
        PATIENT_ID=$patient_id      # e.g. PRV-001-13UL (from grouping)
        LOCAL_DATA_DIR="$HOME/data/$PATIENT_ID"
        
        if [ ! -d "$LOCAL_DATA_DIR" ]; then
            log_message "❌ Merged folder not found at $LOCAL_DATA_DIR after merge_days.py"
            ((failed++))
            continue
        fi

        # ==== STEP 5.5: reorganize for Pennsieve and capture new directory
        # local new_dir
        # new_dir=$(reorganize_folder_structure "$PATIENT_ID" "$LOCAL_DATA_DIR")
        # if [ $? -ne 0 ] || [ -z "$new_dir" ]; then
        #     log_message "Reorganization failed for patient '$patient_id'"
        #     ((failed++))
        #     continue
        # fi
        
        # # Extract the new subject ID from the new directory (PRV-13UL)
        # local final_subject_id=$(basename "$new_dir")
        # log_message "Upload directory: $new_dir (Subject ID: $final_subject_id)"
        
        # ==== STEP 6: upload merged result
        if ! upload_to_pennsieve "$final_subject_id" "$new_dir" "$patient_id" "merged"; then
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
