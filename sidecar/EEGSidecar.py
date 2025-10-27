from jsonschema import Draft202012Validator
from typing import Dict, Any
from Sidecar import Sidecar


class EEGSidecar(Sidecar):
    """
    Represents the eeg.json BIDS sidecar file.

    - Defines required, recommended, and optional fields
    - Validates using JSON Schema + logical BIDS checks
    - Warns on missing recommended or unknown extra fields
    """

    default_filename = "eeg.json"
    default_bids_path = "bids_root/"

    REQUIRED_FIELDS = {
        "TaskName",
        "EEGReference",
        "SamplingFrequency",
        "PowerLineFrequency",
        "SoftwareFilters",
    }

    RECOMMENDED_FIELDS = {
        "TaskDescription",
        "Instructions",
        "CogAtlasID",
        "CogPOID",
        "InstitutionName",
        "InstitutionAddress",
        "InstitutionalDepartmentName",
        "Manufacturer",
        "ManufacturersModelName",
        "SoftwareVersions",
        "DeviceSerialNumber",
        "CapManufacturer",
        "CapManufacturersModelName",
        "EEGGround",
        "EEGChannelCount",
        "ECGChannelCount",
        "EMGChannelCount",
        "EOGChannelCount",
        "MISCChannelCount",
        "TriggerChannelCount",
        "RecordingDuration",
        "RecordingType",
        "HeadCircumference",
        "EEGPlacementScheme",
        "HardwareFilters",
        "SubjectArtefactDescription",
    }

    OPTIONAL_FIELDS = {
        "EpochLength",
        "ElectricalStimulation",
        "ElectricalStimulationParameters",
    }

    DEFAULTS = {
        "TaskName": "default_task",
        "EEGReference": "Cz",
        "SamplingFrequency": 256.0,
        "PowerLineFrequency": 60,
        "SoftwareFilters": "n/a",
        "Manufacturer": "Unknown",
        "ManufacturersModelName": "Unknown",
        "EEGGround": "n/a",
        "RecordingType": "continuous",
        "HeadCircumference": "n/a",
        "ElectricalStimulation": False,
        "Description": "Automatically generated EEG sidecar file.",
    }

    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BIDS EEG JSON Sidecar",
        "type": "object",
        "required": [
            "TaskName",
            "EEGReference",
            "SamplingFrequency",
            "PowerLineFrequency",
            "SoftwareFilters",
        ],
        "properties": {
            "TaskName": {"type": "string"},
            "TaskDescription": {"type": "string"},
            "Instructions": {"type": "string"},
            "CogAtlasID": {"type": "string"},
            "CogPOID": {"type": "string"},
            "InstitutionName": {"type": "string"},
            "InstitutionAddress": {"type": "string"},
            "InstitutionalDepartmentName": {"type": "string"},
            "Manufacturer": {"type": "string"},
            "ManufacturersModelName": {"type": "string"},
            "SoftwareVersions": {"type": "string"},
            "DeviceSerialNumber": {"type": "string"},
            "CapManufacturer": {"type": "string"},
            "CapManufacturersModelName": {"type": "string"},
            "EEGReference": {"type": "string"},
            "EEGGround": {"type": "string"},
            "SamplingFrequency": {"type": "number"},
            "PowerLineFrequency": {
                "oneOf": [{"type": "number"}, {"enum": ["n/a", "N/A"]}]
            },
            "SoftwareFilters": {
                "oneOf": [
                    {"type": "object"},
                    {"enum": ["n/a", "N/A"]},
                ]
            },
            "EEGChannelCount": {"type": "integer"},
            "ECGChannelCount": {"type": "integer"},
            "EMGChannelCount": {"type": "integer"},
            "EOGChannelCount": {"type": "integer"},
            "MISCChannelCount": {"type": "integer"},
            "TriggerChannelCount": {"type": "integer"},
            "RecordingDuration": {"type": "number"},
            "RecordingType": {"type": "string", "enum": ["continuous", "epoched"]},
            "EpochLength": {"type": "number"},
            "HeadCircumference": {"type": ["number", "string"]},
            "EEGPlacementScheme": {"type": "string"},
            "HardwareFilters": {
                "oneOf": [
                    {"type": "object"},
                    {"enum": ["n/a", "N/A"]},
                ]
            },
            "SubjectArtefactDescription": {"type": "string"},
            "ElectricalStimulation": {"type": "boolean"},
            "ElectricalStimulationParameters": {"type": "string"},
        },
        "additionalProperties": True,
    }

    def __init__(self, fields: Dict[str, Any], **kwargs):
        merged_fields = {**self.DEFAULTS, **fields}
        super().__init__(merged_fields, **kwargs)

        self.log.debug(
            f"{self.__class__.__name__} initialized with {len(self.data)} fields "
            f"({len(fields)} user-supplied, {len(self.DEFAULTS)} defaults)."
        )

    def validate(self):
        validator = Draft202012Validator(self.SCHEMA)
        errors = sorted(validator.iter_errors(self.data), key=lambda e: e.path)
        if errors:
            for err in errors:
                self.log.error(f"Schema error at {list(err.path)}: {err.message}")
            raise ValueError(f"{len(errors)} schema validation errors")

        missing_required = self.REQUIRED_FIELDS - self.data.keys()
        missing_recommended = self.RECOMMENDED_FIELDS - self.data.keys()
        extras = set(self.data.keys()) - (
            self.REQUIRED_FIELDS | self.RECOMMENDED_FIELDS | self.OPTIONAL_FIELDS
        )

        # Rule: if RecordingType == "epoched", EpochLength becomes required
        if (
            self.data.get("RecordingType", "").lower() == "epoched"
            and "EpochLength" not in self.data
        ):
            missing_required.add("EpochLength")

        if missing_required:
            raise ValueError(f"Missing REQUIRED fields: {sorted(missing_required)}")

        if missing_recommended:
            self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")

        if extras:
            self.log.warning(f"Extra (non-BIDS) fields found: {sorted(extras)}")

        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
