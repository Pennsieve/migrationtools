from DatsetDescriptionSidecar import DatasetDescriptionSidecar
from SessionsSidecar import SessionSidecar
from ParticipantsSidecar import ParticipantsSidecar
from IEEGSidecar import IeegSidecar
from ChannelsSidecar import ChannelsSidecar
from CoordSystemSidecar import CoordSystemSidecar
from ElectrodesSidecar import ElectrodesSidecar
from EEGSidecar import EEGSidecar
from EventsSidecar import EventsSidecar

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

    channels_data = [
        {
            "name": "EKG1",
            "type": "ECG",
            "units": "uV",
            "low_cutoff": "n/a",
            "high_cutoff": "n/a",
            "reference": "unknown",
            "ground": "unknown",
            "group": "n/a",
            "sampling_frequency": "n/a",
            "notch": "n/a",
        },
        {
            "name": "LA01",
            "type": "SEEG",
            "units": "uV",
            "low_cutoff": "n/a",
            "high_cutoff": 0.01,
            "reference": "LE10",
            "ground": "RF6",
            "group": "LA",
            "sampling_frequency": 256,
            "notch": "n/a",
        },
        {
            "name": "LA02",
            "type": "SEEG",
            "units": "uV",
            "low_cutoff": "n/a",
            "high_cutoff": 0.01,
            "reference": "LE10",
            "ground": "RF6",
            "group": "LA",
            "sampling_frequency": 256,
            "notch": "n/a",
        },
    ]

    sidecar = ChannelsSidecar({})
    ok, report = sidecar.validate(channels_data)

    if ok:
        print("channels.tsv is valid ✅")
    else:
        print("channels.tsv validation failed ❌")
        for e in report["errors"]:
            print("  -", e)

    if report.get("warnings"):
        print("Warnings:")
        for w in report["warnings"]:
            print("  -", w)

    if ok:
        sidecar.save(data=channels_data, output_dir="output/bids/", flat=True)
        print("channels.tsv successfully written to output/bids/")

    coord_fields = {
        "iEEGCoordinateSystem": "fsnative",
        "iEEGCoordinateUnits": "mm",
        "IntendedFor": [
            "sub-01/ses-postimplant/ieeg/sub-01_task-rest_ieeg.json"
        ],
        "iEEGCoordinateSystemDescription": "Subject space registered to preimplant MRI.",
        "iEEGCoordinateProcessingDescription": "Electrode coordinates extracted via Freesurfer.",
        "iEEGCoordinateProcessingReference": "Dale et al., 1999, NeuroImage.",
    }

    sidecar = CoordSystemSidecar(coord_fields)
    if sidecar.validate():
        print("CoordSystemSidecar is valid ✅")
        sidecar.save(output_dir="output/bids", flat=True, json_indent=4)
    else:
        print("CoordSystemSidecar is invalid ❌")

    electrodes_data = [
        {
            "name": "LA01",
            "x": -12.4,
            "y": 44.8,
            "z": 52.1,
            "size": 2.3,
            "material": "platinum",
            "manufacturer": "AD-TECH",
            "group": "LA",
            "hemisphere": "L",
            "type": "SEEG",
            "impedance": 2000,
            "dimension": "mm",
            "roi": "insula",
        },
        {
            "name": "LA02",
            "x": -13.2,
            "y": 46.0,
            "z": 51.5,
            "size": 2.3,
            "material": "platinum",
            "manufacturer": "AD-TECH",
            "group": "LA",
            "hemisphere": "L",
            "type": "SEEG",
            "impedance": 1950,
            "dimension": "mm",
            "roi": "insula",
        },
    ]

    sidecar = ElectrodesSidecar({})
    ok, report = sidecar.validate(electrodes_data)

    if ok:
        print("✅ ElectrodesSidecar is valid.")
        sidecar.save(data=electrodes_data, output_dir="output/bids/", flat=True)
    else:
        print("❌ ElectrodesSidecar validation failed.")
        for err in report["errors"]:
            print("  -", err)

    if report.get("warnings"):
        print("⚠️ Warnings:")
        for warn in report["warnings"]:
            print("  -", warn)

    eeg_fields = {
        "TaskName": "RestingState",
        "EEGReference": "Cz",
        "SamplingFrequency": 500,
        "PowerLineFrequency": 60,
        "SoftwareFilters": "n/a",
        "RecordingType": "continuous",
        "Manufacturer": "BrainProducts",
        "ManufacturersModelName": "actiCHamp",
        "SoftwareVersions": "v2.1.0",
        "EEGChannelCount": 64,
        "EEGPlacementScheme": "10-20 system",
        "SubjectArtefactDescription": "Minor muscle artefacts noted.",
    }

    eeg_sidecar = EEGSidecar(eeg_fields)
    if eeg_sidecar.validate():
        print("✅ EEGSidecar is valid.")
        eeg_sidecar.save(output_dir="output/bids", flat=True, json_indent=4)
    else:
        print("❌ EEGSidecar validation failed.")


    events_data = [
        {
            "onset": 0.0,
            "duration": 1.2,
            "trial_type": "visual",
            "response_time": 0.85,
            "HED": "Sensory-event, Visual, Bright flash",
            "stim_file": "stimulus1.jpg",
            "channel": "EOG",
            "Description": "Visual flash stimulus",
            "Parent": "block_01",
            "Annotated": "true",
            "Annotator": "nishant",
            "Type": "stimulus",
            "Layer": "primary",
        },
        {
            "onset": 2.0,
            "duration": 1.5,
            "trial_type": "auditory",
            "response_time": 1.0,
            "stim_file": "tone.wav",
            "Type": "stimulus",
        },
    ]

    sidecar = EventsSidecar({})
    ok, report = sidecar.validate(events_data)

    if ok:
        print("✅ EventsSidecar is valid.")
        sidecar.save(data=events_data, output_dir="output/bids", flat=True)
    else:
        print("❌ Validation failed:")
        for err in report["errors"]:
            print("  -", err)

    if report.get("warnings"):
        print("⚠️ Warnings:")
        for warn in report["warnings"]:
            print("  -", warn)

main()