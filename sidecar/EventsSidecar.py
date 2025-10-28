import csv
from typing import Dict, Any, List, Tuple
from Sidecar import TSVSidecar


class EventsSidecar(TSVSidecar):
    """
    Represents the events.tsv BIDS sidecar file.
    Stateless — caller provides data (list of dicts).

    Each dict corresponds to one event row.
    """

    default_filename = "events.tsv"
    file_format = "tsv"

    REQUIRED_FIELDS = {"onset", "duration"}
    RECOMMENDED_FIELDS = set()  # none defined explicitly in BIDS
    OPTIONAL_FIELDS = {
        "trial_type",
        "response_time",
        "HED",
        "stim_file",
        "channel",
        "Description",
        "Parent",
        "Annotated",
        "Annotator",
        "Type",
        "Layer",
    }

    def validate(self, data: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the events.tsv structure.

        - Ensures required columns exist
        - Ensures onset/duration are numeric
        - Warns on inconsistent columns or extra fields
        """
        errors, warnings = [], []

        if not isinstance(data, list) or not data:
            return False, {"errors": ["Data must be a non-empty list of dictionaries."]}

        # Gather all columns found in the data
        all_fields = set().union(*(row.keys() for row in data))

        # Presence checks
        missing_required = self.REQUIRED_FIELDS - all_fields
        extra_fields = all_fields - (
            self.REQUIRED_FIELDS | self.RECOMMENDED_FIELDS | self.OPTIONAL_FIELDS
        )

        if missing_required:
            errors.append(f"Missing REQUIRED fields: {sorted(missing_required)}")
        if extra_fields:
            warnings.append(f"Extra (non-BIDS) fields detected: {sorted(extra_fields)}")

        # Consistency checks
        for i, row in enumerate(data):
            if set(row.keys()) != all_fields:
                warnings.append(f"Row {i+1} has inconsistent columns")

        # Numeric validation
        numeric_fields = ["onset", "duration", "response_time"]
        for i, row in enumerate(data):
            for field in numeric_fields:
                val = row.get(field)
                if val not in (None, "n/a", "N/A"):
                    try:
                        float(val)
                    except (TypeError, ValueError):
                        errors.append(
                            f"Row {i+1}: Field '{field}' must be numeric, got '{val}'"
                        )

        ok = not errors
        return ok, {"errors": errors, "warnings": warnings, "columns": sorted(all_fields)}
