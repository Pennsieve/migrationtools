import csv
from typing import Dict, Any, List, Tuple
from Sidecar import Sidecar


class ElectrodesSidecar(Sidecar):
    """
    Represents the electrodes.tsv BIDS sidecar file.
    Stateless — caller provides data (list of dicts).

    Each dict in data corresponds to one electrode row.
    """

    default_filename = "electrodes.tsv"
    file_format = "tsv"

    REQUIRED_FIELDS = {"name", "x", "y", "z", "size"}
    RECOMMENDED_FIELDS = {"material", "manufacturer", "group", "hemisphere"}
    OPTIONAL_FIELDS = {"type", "impedance", "dimension", "roi"}

    def validate(self, data: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the electrodes.tsv structure.

        - Ensures required columns are present.
        - Warns about missing recommended fields.
        - Warns about unexpected columns.
        - Ensures all rows contain consistent keys.
        - Ensures numeric fields contain valid numbers.
        """
        errors, warnings = [], []

        if not isinstance(data, list) or not data:
            return False, {"errors": ["Data must be a non-empty list of dictionaries."]}

        # Gather all columns found in the data
        all_fields = set().union(*(row.keys() for row in data))

        # Field-level presence validation
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

        # Consistency: all rows have same keys
        for i, row in enumerate(data):
            if set(row.keys()) != all_fields:
                warnings.append(f"Row {i+1} has inconsistent columns")

        # Check numeric fields
        numeric_fields = ["x", "y", "z", "size", "impedance"]
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

    def write_data(self, file_path: str, data: List[Dict[str, Any]]):
        """
        Writes the electrodes.tsv file. Each dict represents one electrode row.
        """
        if not data:
            raise ValueError("No data provided to write.")

        fieldnames = [
            "name",
            "x",
            "y",
            "z",
            "size",
            "material",
            "manufacturer",
            "group",
            "hemisphere",
            "type",
            "impedance",
            "dimension",
            "roi",
        ]
        # keep only those present in data
        fieldnames = [f for f in fieldnames if f in data[0]]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(data)

        self.log.debug(f"Wrote electrodes.tsv to {file_path}")
