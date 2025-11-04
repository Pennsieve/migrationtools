from jsonschema import Draft202012Validator
from typing import Dict, Any
from Sidecar import JSONSidecar


class IeegSidecar(JSONSidecar):
    """
    Represents the iEEG BIDS sidecar (e.g., sub-01_task-rest_ieeg.json).

    - Defines a required JSON structure with defaults
    - Allows user overrides for any field
    - Validates using JSON Schema + logical BIDS checks
    - Warns on missing recommended or unknown extra fields
    """

    filename = "ieeg.json"
    bids_path = "bids_root/"

    REQUIRED_FIELDS = {
        "TaskName",
        "PowerLineFrequency",
        "SamplingFrequency",
        "SoftwareFilters",
        "iEEGReference",
    }

    RECOMMENDED_FIELDS = {
        "Manufacturer",
        "ManufacturersModelName",
        "SoftwareVersions",
        "DeviceSerialNumber",
        "HardwareFilters",
        "RecordingDuration",
        "RecordingType",
        "iEEGGround",
        "ECOGChannelCount",
        "SEEGChannelCount",
        "EEGChannelCount",
        "EOGChannelCount",
        "ECGChannelCount",
        "EMGChannelCount",
        "MiscChannelCount",
        "TriggerChannelCount",
        "ElectrodeManufacturer",
        "ElectrodeManufacturersModelName",
        "EpochLength",
        "iEEGPlacementScheme",
        "iEEGElectrodeGroups",
        "SubjectArtefactDescription",
        "TaskDescription",
        "Instructions",
        "CogAtlasID",
        "CogPOID",
        "InstitutionName",
        "InstitutionAddress",
        "InstitutionalDepartmentName",
    }

    OPTIONAL_FIELDS = {
        "ElectricalStimulation",
        "ElectricalStimulationParameters",
    }

    DEFAULTS = {
        "TaskName": "clinical",
        "PowerLineFrequency": 60,
        "SamplingFrequency": "n/a",
        "SoftwareFilters": "n/a",
        "iEEGReference": "unknown",
        "iEEGGround": "unknown",
        "RecordingType": "discontinuous",
        "Manufacturer": "Natus",
        "ManufacturersModelName": "Quantum",
        "InstitutionName": "Penn Medicine",
        "InstitutionAddress": "",
        "InstitutionalDepartmentName": "",
        "ElectrodeManufacturer": "AD-TECH",
        "ElectrodeManufacturersModelName": "",
    }

    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BIDS iEEG Sidecar",
        "type": "object",
        "required": [
            "TaskName",
            "PowerLineFrequency",
            "SamplingFrequency",
            "SoftwareFilters",
            "iEEGReference",
        ],
        "properties": {
            "TaskName": {"type": "string"},
            "PowerLineFrequency": {"type": "number"},
            "SamplingFrequency": {"type": "number"},
            "SoftwareFilters": {"type": ["string", "object"]},
            "iEEGReference": {"type": "string"},
            "iEEGGround": {"type": "string"},
            "Manufacturer": {"type": "string"},
            "ManufacturersModelName": {"type": "string"},
            "RecordingDuration": {"type": ["number", "null"]},
            "RecordingType": {"type": "string"},
            "ElectricalStimulation": {"type": ["boolean", "string"]},
            "InstitutionName": {"type": "string"},
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
        """
        Validates the iEEG sidecar JSON structure.
        Combines JSON Schema validation with BIDS-specific field checks.
        """
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

        if missing_required:
            raise ValueError(f"Missing REQUIRED fields: {sorted(missing_required)}")

        if missing_recommended:
            self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")

        if extras:
            self.log.warning(f"Extra (non-BIDS) fields found: {sorted(extras)}")

        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
