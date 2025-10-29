from jsonschema import Draft202012Validator
from typing import Dict, Any
from .Sidecar import Sidecar 

class EegJSON(Sidecar):
    """
    Represents the eegJSON.json BIDS sidecar.

    - Defines a required JSON structure with defaults
    - Allows user overrides for any field
    - Validates using JSON Schema + logical BIDS checks
    - Warns on missing recommended or unknown extra fields
    """

    default_filename = "eeg.json" # need to change according to the format "sub-PRV-<patient_id>-<age>_task-rest_eeg.json"
    default_bids_path = "output_sidecars/"

    REQUIRED_FIELDS = {
        "TaskName", 
        "TaskDescription",
        "EEGReference",
        "EEGGround",
        "SamplingFrequency",
        "PowerLineFrequency",
        "SoftwareFilters",
    }

    RECOMMENDED_FIELDS = {
        "InstitutionName",
        "Manufacturer",
        "EEGChannelCount",
        "ECGChannelCount",
        "EMGChannelCount",
        "EOGChannelCount",
        "MiscChannelCount",
        "TriggerChannelCount",
        "RecordingDuration",
        "RecordingType",
        "EEGPlacementScheme",
        "HardwareFilters",
    }
    
    OPTIONAL_FIELDS = {
        "ManufacturerModelName",
        "SubjectArtefactDescription",
    }

    DEFAULTS = {
        # Required fields with static defaults
        "TaskName": "PRV",
        "TaskDescription": "All video EEG studies will be recorded for one hour, incorporating both 20mins of sleep and wakefulness. Recordings can be up to 80min to attempt to capture sleep",
        "EEGReference": "Slightly anterior and slightly left of the Cz electrode",
        "EEGGround": "Slightly anterior and slightly right of the Cz electrode",
        "SamplingFrequency": -1,
        "PowerLineFrequency": 60,
        "SoftwareFilters": {
            "Anti-aliasing filter": {
                "half-amplitude cutoff (Hz)": 500
            }
        },
        # Recommended fields
        "InstitutionName": "",
        "Manufacturer": "",
        "EEGChannelCount": -1,
        "ECGChannelCount": -1,
        "EMGChannelCount": -1,
        "EOGChannelCount": -1,
        "MiscChannelCount": -1,
        "TriggerChannelCount": -1,
        "RecordingDuration": -1,
        "RecordingType": "continuous",
        "EEGPlacementScheme": "",
        "HardwareFilters": {},
        # Optional fields
        "ManufacturerModelName": "",
        "SubjectArtefactDescription": "",
        # Note: Fields with None are excluded - they should be provided when creating the sidecar
        # "SamplingFrequency": None,  # Must be provided from EDF
        # "EEGChannelCount": None,
        # "ECGChannelCount": None,
        # "EMGChannelCount": None,
        # "EOGChannelCount": None,
        # "MiscChannelCount": None,
        # "TriggerChannelCount": None,
        # "RecordingDuration": None,
    }

    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BIDS EEG Metadata",
        "type": "object",
        "required": ["TaskName", "SamplingFrequency", "PowerLineFrequency", "EEGReference"],
        "properties": {
            # Required fields
            "TaskName": {"type": "string"},
            "TaskDescription": {"type": "string"},
            "EEGReference": {"type": "string"},
            "EEGGround": {"type": "string"},
            "SamplingFrequency": {"type": "number", "minimum": 0},
            "PowerLineFrequency": {"type": "number", "enum": [50, 60]},
            "SoftwareFilters": {"type": "object"},
            
            # Recommended fields
            "InstitutionName": {"type": "string"},
            "Manufacturer": {"type": "string"},
            "EEGChannelCount": {"type": "integer", "minimum": 0},
            "ECGChannelCount": {"type": "integer", "minimum": 0},
            "EMGChannelCount": {"type": "integer", "minimum": 0},
            "EOGChannelCount": {"type": "integer", "minimum": 0},
            "MiscChannelCount": {"type": "integer", "minimum": 0},
            "TriggerChannelCount": {"type": "integer", "minimum": 0},
            "RecordingDuration": {"type": "number", "minimum": 0},
            "RecordingType": {"type": "string", "enum": ["continuous", "discontinuous", "epoched"]},
            "EEGPlacementScheme": {"type": "string"},
            "HardwareFilters": {"type": "object"},
            
            # Optional fields
            "ManufacturersModelName": {"type": "string"},
            "SubjectArtefactDescription": {"type": "string"},
            "Impedance": {"type": "number", "minimum": 0},
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
            print(errors)
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
