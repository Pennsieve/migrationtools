# Generates sidecar CSV files for iEEG data migration
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from logger.setup_logger import setup_logger

import os
import csv
import argparse
import json
import string

log = setup_logger("find_ref_gnd")
log.info("#### Logger initialized for generate_csv_files ####")


# Key value store for common data across sidecar files
common_data ={}

BIDS_VERSION = "1.7.0-PENN"
DATASET_TYPE = "raw" # TODO: confirm value
LICENSE = "CC-BY"
AUTHORS = ["Nishant Sinha", "Erin Conrad", "M.D., Kathryn A Davis", "Brian Litt"] # TODO: confirm authors
KEYWORDS = ["epilepsy", "intracranial", "human", "adult", "epilepsy.science"]
ACKNOWLEDGEMENTS = "This dataset was prepared by the iEEG-BIDS Migration Tool developed at the University of Pennsylvania." # TODO: confirm acknowledgements
HOW_TO_ACKNOWLEDGE = "Please cite the iEEG-BIDS Migration Tool paper when using this dataset." # TODO: confirm how to acknowledge
FUNDING = [
    "National Institue of Neurological Disorders and Stroke of the National Institutes of Health K99NS138680",
    "National Institue of Neurological Disorders and Stroke of the National Institutes of Health R01NS125137",
    "National Institue of Neurological Disorders and Stroke of the National Institutes of Health R01NS116504",
    "National Institue of Neurological Disorders and Stroke of the National Institutes of Health U24NS134536",
    ] # TODO: confirm funding
EHTICS_APPROVALS = ["University of Pennsylvania Human Research Protections Program, Intstitutional Review Boards (Protocol ABC, XYZ, 123)"] #TODO confirm ethics approvals
REFERENCE_AND_LINKS = "" # TODO: confirm reference
DATASE_DOI = ""
GENERATED_BY = [
    {
        "Name": "iEEG-BIDS Migration Tool",
        "Version": "1.0.0",
        # TODO: add more fields if needed
    }
]
DESCRIPTION = "" # TODO: confirm description

def write_csv(new_name, headers, rows, sidecar_filename,filetype="csv"):
    output_dir = f"ieeg_sidescar_file_output/{new_name}"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, sidecar_filename)
    delimiter = "," if filetype == "csv" else "\t"
    with open(file_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(headers)
        writer.writerows(rows)

def write_json(new_name, json_structure,side_car_filename):
    output_dir = f"ieeg_sidescar_file_output/{new_name}"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, side_car_filename), "w", encoding="utf-8") as f:
        json.dump(json_structure, f, indent=4)

def get_name():
    _ = common_data["current_input"]["label"]
    _ = common_data["current_input"]["Number only"].translate(str.maketrans('', '', string.whitespace + string.punctuation))
    eps_number = common_data["current_input"]["EPS Number"].lower().strip("eps").lstrip("0").zfill(5)

    new_name = f"PENNEPI{eps_number}"
    return new_name

def handle_dataset_description_json():
    log.info("Handling dataset_description.json sidecar...")

    json_structure = {
        "Name": f"{common_data["new_name"]}", 
        "BIDSVersion": BIDS_VERSION,
        "DatasetType": DATASET_TYPE,
        "License": LICENSE,
        "Authors": AUTHORS,
        "Acknowledgements": ACKNOWLEDGEMENTS,
        "HowToAcknowledge": HOW_TO_ACKNOWLEDGE,
        "Funding": FUNDING,
        "EthicsApprovals": EHTICS_APPROVALS,
        "ReferencesAndLinks": REFERENCE_AND_LINKS,
        "DatasetDOI": DATASE_DOI,
        "GeneratedBy": GENERATED_BY,
        "Description": DESCRIPTION,
    }

    write_json(common_data["new_name"], json_structure,"dataset_description.json")


def handle_participants_json(write=True):
    """Create or update participants.json sidecar (stub)."""
    json_structure = {
        "participant_id": {
            "Description": "Unique participant identifier",
            "Units": "String" # TODO: confirm units
        },
        "species": {
            "Description": "Species of the participant",
            "Units": "homo sapien",
        },
        "age": {
            "Description": "Age of the participant at tghe time of testing",
            "Units": "year" # TODO: should this be months?
        },
        "population": {
            "Description": "Adult or pediatric",
            "Levels": {
                "A": "adult",
                "P": "pediatric"
            }
        },
        "sex": {
            "Description": "Biological sex of the participant",
            "Levels": {
                "M": "male",
                "F": "female"
            }
        },
        "handedness": {
            "Description": "Handedness of the participant",
            "Levels": {
                "L": "left",
                "R": "right"
            }
        },
    }
    if write:
        write_json(common_data["new_name"], json_structure,"participants.json")
    else:
        return json_structure

def get_participants_tsv_data():
    common_data["age"] = 30
    return [f"sub-{common_data["new_name"]}", "homo sapien", common_data["age"], "A", "M", "R"]  # Example data; replace with actual logic

def handle_participants_tsv():
    log.info("Creating participants.tsv sidecar")

    row_header = handle_participants_json(write=False).keys()
    row_data = get_participants_tsv_data()

    write_csv(common_data["new_name"], row_header, [row_data], "participants.tsv","tsv")

def get_session_info():
    sesion_info = [
        ["ses-postimplant","intracranial evaluation","seeg_age_implant","",""],
        ["ses-postsurgery","post surgical treatment follow up, no sooner than 15months ","procedure_age","",""],
        ["ses-preimplant","medical history and data leading up to intracranial evaluation","n/a","NEED TO ASK NISHANT","NEED TO ASK NISHANT"]
    ]
    return sesion_info
def handle_sessions_tsv():
    log.info("Creating sessions.tsv")

    row_header = ["session_id", "session_description","subject_age_at_session","age_at_preimplant", "age_at_eeg"]
    row_data = get_session_info()

    write_csv(common_data["new_name"], row_header, row_data, "sessions.tsv","tsv")

def handle_ieeg_json():
    log.info("Creating ieeg.json sidecar")

    json_structure = {
        "TaskName": "clinical",
        "TaskDescription": "IEEG monitoring for diagnostic clinical purposes, secondary use of clinical data for research purposes",
        "InstitutionName": "PennMedicine",
        "Manufacturer": "Natus", # TODO: import from CSV
        "ManufacturersModelName": "Natus Quantum", # TODO: import from CSV
        "ElectrodeManufacturer": "AD-TECH", # TODO: import from CSV
        "iEEGReference": "LE10", # TODO: import from CSV
        "iEEGGround": "RF6", # TODO: import from CSV
        "SamplingFrequency": 256, # TODO: import MEF HEADER / current ieeg.json on Pennsieve
        "PowerLineFrequency": 60,
        "SoftwareFilters": "n/a",
        "HardwareFilters": {
            "Highpass filter": "0.01 Hz" # TODO: import from CSV
        },
        "ECOGChannelCount": 0,
        "SEEGChannelCount": 124,
        "EEGChannelCount": 0,
        "EOGChannelCount": 0,
        "ECGChannelCount": 0,
        "EMGChannelCount": 0,
        "MiscChannelCount": 0,
        "TriggerChannelCount": 0,
        "RecordingDuration": "autogenerated", # TODO: import MEF HEADER / current ieeg.json on Pennsieve
        "RecordingType": "discontinuous",
        "iEEGPlacementScheme": "", # From CSV optional
        "iEEGElectrodeGroups": "", # From CSV optional
        "ElectricalStimulation": False # TODO: import from CSV
    }

    write_json(common_data["new_name"], json_structure,"ieeg.json")



def handle_channels_tsv():
    """Create or update channels.tsv sidecar (stub)."""
    pass

def handle_electrodes_tsv():
    """Create or update electrodes.tsv sidecar (stub)."""
    pass

def handle_space_native_coordsystem_json():
    log.info("Creating space-native_coordsystem.json sidecar")

    json_structure = {
        "IntendedFor": "URI to patient space in freesurfer derivative (URI) preimplant; nishant to generate", # TODO: confirm source
        "iEEGCoordinateSystem": "maybe fsLR",
        "iEEGCoordinateUnits": "mm",
        "iEEGCoordinateSystemDescription": "description like \"patient space in freesurfer derivative preimplant\"",
        "iEEGCoordinateProcessingDescription": "need from nishant",
        "iEEGCoordinateProcessingReference": "citation"
    }
    write_json(common_data["new_name"], json_structure,"space-native_coordsystem.json")

def handle_space_native_electrodes_tsv():
    """Create or update space-native_electrodes.tsv sidecar (stub)."""
    pass

def handle_derivatives_dataset_description_json():
    log.info("Creating derivatives_dataset_description.json sidecar")

    json_structure = {
        "Name": f"{common_data["new_name"]}", 
        "BIDSVersion": BIDS_VERSION,
        "DatasetType": DATASET_TYPE,
        "License": LICENSE,
        "Authors": AUTHORS,
        "Acknowledgements": ACKNOWLEDGEMENTS,
        "HowToAcknowledge": HOW_TO_ACKNOWLEDGE,
        "Funding": FUNDING,
        "EthicsApprovals": EHTICS_APPROVALS,
        "ReferencesAndLinks": REFERENCE_AND_LINKS,
        "DatasetDOI": DATASE_DOI,
        "GeneratedBy": GENERATED_BY,
        "Description": DESCRIPTION,
    }

    write_json(common_data["new_name"], json_structure,"derivative_dataset_description.json")

def open_input(file_path):
    log.info(f"Opening input file: {file_path}")
    try:
        with open(file_path, newline='') as fh:
            reader = csv.DictReader(fh)
            data = [row for row in reader]
    except FileNotFoundError:
        log.error("Input file not found: %s", file_path)
        return None
    except Exception as exc:
        log.exception("Failed to read input file %s: %s", file_path, exc)
        return None

    log.info("Loaded %d rows from input file %s", len(data), file_path)
    return data

# Mapping from sidecar filename -> handler function
SIDECAR_HANDLERS = {
    "dataset_description.json": handle_dataset_description_json,
    "participants.json": handle_participants_json,
    "participants.tsv": handle_participants_tsv,
    "sessions.tsv": handle_sessions_tsv,
    "ieeg.json": handle_ieeg_json,
    "channels.tsv": handle_channels_tsv,
    "electrodes.tsv": handle_electrodes_tsv,
    "space-native_coordsystem.json": handle_space_native_coordsystem_json,
    "space-native_electrodes.tsv": handle_space_native_electrodes_tsv,
    "derivatives_dataset_description.json": handle_derivatives_dataset_description_json, # skip?
}

def main():
    log.info("Starting CSV generation for iEEG migration...")
    inputs = open_input("input/inputs.csv")
    for input in inputs:
        common_data["current_input"] = input
        common_data["new_name"] = get_name()
        for sidecar_filename, handler in SIDECAR_HANDLERS.items():
            log.info(f"Processing sidecar file: {sidecar_filename}")
            handler()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sidecar files")
    parser.add_argument(
        "--output", "-o", required=True,
        help="Path to output CSV file (e.g., /path/to/ref_gnd_summary.csv)"
    )

    main()