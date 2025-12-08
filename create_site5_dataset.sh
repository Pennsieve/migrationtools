# list of patient id
PATIENT_IDS=(
    "1PPT"
    "2RS7"
    "3UMP"
    "4G5F"
    "54NA"
    "5JPD"
    "6A9Y"
    "6APN"
    "7K4C"
    "7TA7"
)

create_dataset_on_pennsieve() {
    local patient_id="$1"
    local dataset_name="PREVeNT Trial $patient_id"

    # Create dataset description and tags
    local description="PREVeNT Trial: Preventing Epilepsy Using Vigabatrin in Infants with Tuberous Sclerosis Complex"
    local tags='["epilepsy.science", "PREVeNT Trial", "eeg", "pediatric", "tuberous sclerosis complex", "preventing epilepsy", "developmental outcomes", "vigabatrin", "human"]'

    # === Create Pennsieve dataset ===
    echo "--------------------------------"
    echo "Creating Pennsieve dataset: $dataset_name"
    local create_output

    if ! create_output=$(pennsieve dataset create "$dataset_name" "$description" "$tags" 2>&1); then
        echo "[ERROR]: Failed to create dataset '$dataset_name'"
        return 1
    fi

    echo "[SUCCESS]: Created dataset '$dataset_name'"
    echo "$create_output"
}

# Main execution
for patient_id in "${PATIENT_IDS[@]}"; do
    create_dataset_on_pennsieve "$patient_id"
done
    