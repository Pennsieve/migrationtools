from jsonschema import Draft202012Validator
from typing import Dict, Any
from Sidecar import JSONSidecar


class ParticipantsSidecar(JSONSidecar):
    """
    Represents the participants.json BIDS sidecar.

    Each key describes a column in participants.tsv.
    Provides validation for REQUIRED, RECOMMENDED, and OPTIONAL fields,
    with JSON schema structural validation.
    """

    filename = "participants.json"
    bids_path = "bids_root/"

    REQUIRED_FIELDS = {"participant_id"}
    RECOMMENDED_FIELDS = {
        "species",
        "age",
        "sex",
        "handedness",
        "strain",
        "strain_rrid",
    }
    OPTIONAL_FIELDS = {"HED"}  # plus any other user-supplied columns

    # Default field templates based on BIDS spec
    DEFAULTS = {
        "participant_id": {
            "Description": "Unique participant identifier",
            "Units": "string",
        },
        "species": {
            "Description": "Species of the participant",
            "Units": "Homo sapiens",
        },
        "age": {
            "Description": "Age of the participant at the time of testing",
            "Units": "years",
        },
        "population": {
            "Description": "Adult or pediatric",
            "Levels": {
                "A": "adult",
                "P": "pediatric"
            },
        },
        "sex": {
            "Description": "Biological sex of the participant",
            "Levels": {
                "M": "male",
                "F": "female"
            },
        },
        "handedness": {
            "Description": "Handedness of the participant",
            "Levels": {
                "L": "left",
                "R": "right"
            },
        },
    }

    # Basic JSON Schema for structure validation
    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BIDS Participants JSON",
        "type": "object",
        "patternProperties": {
            "^[a-zA-Z0-9_]+$": {  # field names
                "type": "object",
                "properties": {
                    "Description": {"type": "string"},
                    "Units": {"type": "string"},
                    "Levels": {"type": "object"},
                },
                "additionalProperties": True,
            }
        },
        "additionalProperties": True,
    }

    def __init__(self, fields: Dict[str, Any], **kwargs):
        merged_fields = {**self.DEFAULTS, **fields}
        super().__init__(merged_fields, **kwargs)

        self.log.debug(
            f"{self.__class__.__name__} initialized with {len(self.data)} participant attributes "
            f"({len(fields)} user-supplied, {len(self.DEFAULTS)} defaults)."
        )

    def validate(self):
        """Validate JSON structure and required/recommended fields."""
        validator = Draft202012Validator(self.SCHEMA)
        errors = sorted(validator.iter_errors(self.data), key=lambda e: e.path)

        if errors:
            for err in errors:
                self.log.error(f"Schema error at {list(err.path)}: {err.message}")
            raise ValueError(f"{len(errors)} schema validation errors")

        # Logical BIDS-level checks
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
            self.log.info(f"Additional user-defined fields detected: {sorted(extras)}")

        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
