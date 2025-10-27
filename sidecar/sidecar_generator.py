from DatsetDescriptionSidecar import DatasetDescriptionSidecar
from SessionsSidecar import SessionSidecar
from ParticipantsSidecar import ParticipantsSidecar
from IEEGSidecar import IeegSidecar

def main():
    dd_sidecar = DatasetDescriptionSidecar({
        "Name": f"Sample Dataset", 
        "BIDSVersion": "BIDS_VERSION",
        "DatasetType": "raw",
        "License": "LICENSE",
        "Authors": ["ME","AND","YOU", "AND","ZOBOOMAFOO"],
        "Acknowledgements": "ACKNOWLEDGEMENTS",
        "HowToAcknowledge": "HOW_TO_ACKNOWLEDGE",
        "Funding": ["FUNDING_1", "FUNDING_2"],
        "EthicsApprovals": ["ETHICS_APPROVAL_1"],
        "ReferencesAndLinks": "REFERENCE_AND_LINKS",
        "DatasetDOI": "DATASE_DOI",
        "GeneratedBy": [{
            "Name": "iEEG-BIDS Migration Tool",
            "Version": "1.0.0"
        }],
        "Description": "DESCRIPTION",
    })
    if dd_sidecar.validate():
        print("DatasetDescriptionSidecar is valid.")
        dd_sidecar.save(output_dir="output/bids", flat=True, json_indent=4)
    else:
        print("DatasetDescriptionSidecar is invalid.")

    participants_sidecar = ParticipantsSidecar({
        "participant_id": {
            "Description": "Unique participant identifier",
            "Units": "string"
        },
        "species": {
            "Description": "Species of the participant",
            "Units": "Homo sapiens"
        },
        "age": {
            "Description": "Age of the participant at the time of testing",
            "Units": "years"
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
        "strain": {
            "Description": "Strain or subspecies of the participant (if applicable)",
            "Units": "string"
        },
        "strain_rrid": {
            "Description": "Research Resource Identifier for the strain",
            "Units": "RRID:____"
        },
        "HED": {
            "Description": "Hierarchical Event Descriptors for this participant metadata",
            "Units": "HED tag string (optional)"
        }
        })
    if participants_sidecar.validate():
        print("DatasetDescriptionSidecar is valid.")
        participants_sidecar.save(output_dir="output/bids", flat=True, json_indent=4)
    else:
        print("DatasetDescriptionSidecar is invalid.")

    sessions_data = [
        {
            "session_id": "ses-preimplant",
            "acq_time": "2024-10-15T09:00:00",
            "session_description": "Pre-surgical EEG recording",
            "task": "resting",
            "age": 34,
            "sex": "M",
        },
        {
            "session_id": "ses-postimplant",
            "acq_time": "2024-10-16T10:30:00",
            "session_description": "Post-surgical stimulation test",
            "task": "stimulation",
            "age": 35,
            "sex": "M",
        },
    ]
    session_sidecar = SessionSidecar({})

    # Run validation
    ok, report = session_sidecar.validate(sessions_data)

    # Print validation feedback
    if ok:
        print("SessionSidecar is valid.")
    else:
        print("SessionSidecar validation failed.")
        if report.get("errors"):
            print("Errors:")
            for err in report["errors"]:
                print("  -", err)
    if report.get("warnings"):
        print("Warnings:")
        for warn in report["warnings"]:
            print("  -", warn)

    # Save file if validation passes
    if ok:
        session_sidecar.save(data=sessions_data, output_dir="output/bids/", flat=True)
        print("sessions.tsv successfully written to output/bids/")
    else:
        print("Skipping save due to validation errors.")

def main():
    ieeg_data = {
        "TaskName": "clinical_monitoring",
        "PowerLineFrequency": 60,
        "SamplingFrequency": 256,
        "SoftwareFilters": "n/a",
        "iEEGReference": "LE10",
        "iEEGGround": "RF6",
        "Manufacturer": "Natus",
        "ManufacturersModelName": "Quantum",
        "InstitutionName": "Penn Medicine",
        "RecordingDuration": 3600,
        "RecordingType": "continuous",
        "ECOGChannelCount": 32,
        "SEEGChannelCount": 64,
        "EEGChannelCount": 0,
        "ElectrodeManufacturer": "AD-TECH",
        "ElectrodeManufacturersModelName": "SDE",
    }

    sidecar = IeegSidecar(ieeg_data)
    is_valid = sidecar.validate()

    if is_valid:
        print("iEEG Sidecar is valid ✅")
    else:
        print("IeegSidecar is invalid.")

    # Save only if validation passed
    if is_valid:
        sidecar.save( output_dir="output/bids", flat=True)
        print("Saved ieeg.json successfully.")


main()