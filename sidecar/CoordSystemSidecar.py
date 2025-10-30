from jsonschema import Draft202012Validator
from typing import Dict, Any
from Sidecar import JSONSidecar


class CoordSystemSidecar(JSONSidecar):
    """
    Represents the iEEG coordinate system sidecar (e.g., space-native_coordsystem.json).

    - Defines required and recommended fields per BIDS iEEG specification
    - Merges user fields with defaults
    - Validates using JSON Schema + BIDS logical rules
    - Warns on missing recommended fields or unknown extras
    """

    filename = "coordsystem.json"
    bids_path = "bids_root/"

    REQUIRED_FIELDS = {
        "iEEGCoordinateSystem",
        "iEEGCoordinateUnits",
    }

    RECOMMENDED_FIELDS = {
        "iEEGCoordinateSystemDescription",
        "iEEGCoordinateProcessingDescription",
        "iEEGCoordinateProcessingReference",
    }

    OPTIONAL_FIELDS = {
        "IntendedFor",
    }

    DEFAULTS = {
        "iEEGCoordinateSystem": "fsnative",
        "iEEGCoordinateUnits": "mm",
        "iEEGCoordinateSystemDescription": "Native FreeSurfer surface space.",
        "iEEGCoordinateProcessingDescription": "Processed using FreeSurfer recon-all pipeline.",
        "iEEGCoordinateProcessingReference": "Dale, A.M., Fischl, B., Sereno, M.I., 1999. Cortical surface-based analysis. NeuroImage.",
    }

    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BIDS iEEG Coordinate System Sidecar",
        "type": "object",
        "required": ["iEEGCoordinateSystem", "iEEGCoordinateUnits"],
        "properties": {
            "IntendedFor": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}}
                ]
            },
            "iEEGCoordinateSystem": {"type": "string"},
            "iEEGCoordinateUnits": {"type": "string"},
            "iEEGCoordinateSystemDescription": {"type": "string"},
            "iEEGCoordinateProcessingDescription": {"type": "string"},
            "iEEGCoordinateProcessingReference": {"type": "string"},
        },
        "additionalProperties": True,
    }

    def __init__(self, fields: Dict[str, Any], **kwargs):
        # Merge user-provided values with defaults
        merged_fields = {**self.DEFAULTS, **fields}
        super().__init__(merged_fields, **kwargs)

        self.log.debug(
            f"{self.__class__.__name__} initialized with {len(self.data)} fields "
            f"({len(fields)} user-supplied, {len(self.DEFAULTS)} defaults)."
        )

    def validate(self):
        """
        Validate the coord system JSON file against schema and BIDS field logic.
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

        # Special case: if iEEGCoordinateSystem == "Other", description is required
        if (
            self.data.get("iEEGCoordinateSystem", "").lower() == "other"
            and "iEEGCoordinateSystemDescription" not in self.data
        ):
            missing_required.add("iEEGCoordinateSystemDescription")

        if missing_required:
            raise ValueError(f"Missing REQUIRED fields: {sorted(missing_required)}")

        if missing_recommended:
            self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")

        if extras:
            self.log.warning(f"Extra (non-BIDS) fields found: {sorted(extras)}")

        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
