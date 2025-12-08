#!/usr/bin/env python3
"""
Generate BIDS dataset_description.json sidecar files.
Creates dataset_description.json for each patient/dataset.
"""

from sidecar.datasetDescriptionJSON import DatasetDescriptionJSON


def handle_dataset_description(patient_id, output_base_dir):
    """
    Generate dataset_description.json for a specific patient/dataset.

    Args:
        patient_id: Patient identifier (e.g., "4ZHY")
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """
    # Build the dataset name
    dataset_name = f"PREVeNT Trial {patient_id}"

    # Create the dataset description with only the Name field
    # (all other fields use defaults from DatasetDescriptionJSON)
    fields = {
        "Name": dataset_name
    }

    # Calculate bids_path: PREVeNT Trial {patient_id}/
    bids_path = f"PREVeNT Trial {patient_id}/"

    # Create sidecar
    dataset_description = DatasetDescriptionJSON(
        fields=fields,
        bids_path=bids_path,
        filename="dataset_description.json"
    )

    # Validate and save
    try:
        if dataset_description.validate():
            saved_path = dataset_description.save(output_dir=output_base_dir)
            print(f"    \u2713 Saved: {saved_path}")
            return True
    except Exception as e:
        print(f"    \u2717 Error: {e}")
        return False
