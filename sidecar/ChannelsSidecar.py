import csv
from typing import Dict, Any, List, Tuple
from Sidecar import TSVSidecar


class ChannelsSidecar(TSVSidecar):
    """
    Represents the channels.tsv BIDS sidecar file.

    Stateless — caller provides data (list of dicts).
    Each row corresponds to one recorded channel.
    """

    filename = "channels.tsv"
    file_format = "tsv"

    # Field definitions based on BIDS iEEG specification
    REQUIRED_FIELDS = {
        "name",
        "type",
        "units",
        "sampling_frequency",
        "low_cutoff",
        "high_cutoff",
        "notch",
        "reference",
        "group",
    }

    RECOMMENDED_FIELDS = set()  # none strictly recommended by spec
    OPTIONAL_FIELDS = {
        "description",  # free text column for optional notes
    }

    def validate(self, data: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the channels.tsv structure.

        - Ensures required columns are present.
        - Warns about missing optional fields.
        - Warns about unexpected columns.
        - Ensures all rows have consistent keys.
        - Checks that numeric columns contain numeric-like values.
        """
        errors, warnings = [], []

        if not isinstance(data, list) or not data:
            return False, {"errors": ["Data must be a non-empty list of dictionaries."]}

        all_fields = set().union(*(row.keys() for row in data))

        # Field presence validation
        missing_required = self.REQUIRED_FIELDS - all_fields
        extra_fields = all_fields - (
            self.REQUIRED_FIELDS | self.RECOMMENDED_FIELDS | self.OPTIONAL_FIELDS
        )

        if missing_required:
            errors.append(f"Missing REQUIRED fields: {sorted(missing_required)}")

        if extra_fields:
            warnings.append(f"Extra (non-BIDS) fields detected: {sorted(extra_fields)}")

        # Consistency check — all rows have same fields
        for i, row in enumerate(data):
            if set(row.keys()) != all_fields:
                warnings.append(f"Row {i+1} has inconsistent columns")

        # Check numeric fields for proper format
        numeric_fields = ["low_cutoff", "high_cutoff", "sampling_frequency", "notch"]
        for field in numeric_fields:
            for i, row in enumerate(data):
                val = row.get(field, None)
                if val not in (None, "n/a", "N/A"):
                    try:
                        float(val)
                    except (TypeError, ValueError):
                        warnings.append(f"Row {i+1}: Field '{field}' should be numeric, got '{val}'")

        ok = not errors
        return ok, {"errors": errors, "warnings": warnings, "columns": sorted(all_fields)}
