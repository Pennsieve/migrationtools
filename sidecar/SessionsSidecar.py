from typing import Dict, Any, List, Tuple
from Sidecar import TSVSidecar


class SessionSidecar(TSVSidecar):
    """
    Represents the sessions.tsv sidecar file.
    Stateless — caller provides data (list of dicts).

    Each dict in data corresponds to one row.
    """

    filename = "sessions.tsv"
    file_format = "tsv"

    REQUIRED_FIELDS = {"session_id"}
    RECOMMENDED_FIELDS = {"acq_time", "session_description"}
    OPTIONAL_FIELDS = {"task", "age", "sex"}

    def validate(self, data: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the sessions.tsv structure.

        - Ensures required columns are present.
        - Warns about missing recommended fields.
        - Warns about unexpected columns.
        - Ensures all rows contain consistent keys.
        """
        errors, warnings = [], []

        if not isinstance(data, list) or not data:
            return False, {"errors": ["Data must be a non-empty list of dictionaries."]}

        # Gather all columns found in the data
        all_fields = set().union(*(row.keys() for row in data))

        # Validation checks
        missing_required = self.REQUIRED_FIELDS - all_fields
        missing_recommended = self.RECOMMENDED_FIELDS - all_fields
        extra_fields = all_fields - (
            self.REQUIRED_FIELDS | self.RECOMMENDED_FIELDS | self.OPTIONAL_FIELDS
        )

        if missing_required:
            errors.append(f"Missing REQUIRED fields: {sorted(missing_required)}")

        if missing_recommended:
            warnings.append(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")

        if extra_fields:
            warnings.append(f"Extra (non-BIDS) fields detected: {sorted(extra_fields)}")

        # Ensure all rows have the same keys
        expected_cols = list(all_fields)
        for i, row in enumerate(data):
            if set(row.keys()) != all_fields:
                warnings.append(f"Row {i+1} has inconsistent columns")

        ok = not errors
        return ok, {"errors": errors, "warnings": warnings, "columns": expected_cols}
