from typing import Dict, Any, List
from .Sidecar import Sidecar


class SessionsTSV(Sidecar):
    """
    Represents the sessions.tsv BIDS sidecar.
    
    TSV format for session-level metadata.
    Data should be a list of dictionaries, where each dictionary represents a row.
    """

    default_filename = "sessions.tsv"
    default_bids_path = "output_sidecars/"

    REQUIRED_FIELDS = {"session", "age_in_months", "visit_type"}
    RECOMMENDED_FIELDS = set()
    OPTIONAL_FIELDS = set()

    # For TSV, defaults don't make sense since each row is different
    DEFAULTS = {}

    def __init__(self, fields: List[Dict[str, Any]], **kwargs):
        """
        Initialize SessionsTSV with a list of session dictionaries.
        
        Args:
            fields: List of dictionaries, each representing a session row
                   Example: [
                       {"session": "ses-visit-m15", "visit_type": "baseline", "age_in_months": 15},
                       {"session": "ses-visit-m18", "visit_type": "followup", "age_in_months": 18}
                   ]
        """
        if not isinstance(fields, list):
            raise TypeError("SessionsTSV requires fields to be a list of dictionaries")
        
        # For TSV sidecars, we store the list directly as data
        # Skip the normal Sidecar.__init__ merge logic
        self.log = self.get_logger()
        
        path_defaults = {"bids_path": self.default_bids_path}
        merged_paths = {**path_defaults, **kwargs}
        
        self.paths = {k: v for k, v in merged_paths.items() if k in self.excluded_fields}
        self.data = fields  # Store list directly
        
        # Handle custom filename if provided
        if "filename" in kwargs:
            self.default_filename = kwargs["filename"]
        
        self.json_indent = kwargs.pop("json_indent", self.json_indent)
        
        self.log.debug(
            f"{self.__class__.__name__} initialized with {len(self.data)} rows"
        )

    def validate(self):
        """
        Validate the sessions.tsv data structure.
        """
        if not isinstance(self.data, list) or not self.data:
            raise ValueError("SessionsTSV data must be a non-empty list of dictionaries")
        
        # Check that all rows have the same columns
        if self.data:
            first_keys = set(self.data[0].keys())
            for i, row in enumerate(self.data):
                if set(row.keys()) != first_keys:
                    raise ValueError(f"Row {i} has inconsistent columns: {set(row.keys())} vs {first_keys}")
        
        # Check for required fields in all rows
        for i, row in enumerate(self.data):
            missing_required = self.REQUIRED_FIELDS - row.keys()
            if missing_required:
                raise ValueError(f"Row {i} missing REQUIRED fields: {sorted(missing_required)}")
        
        # Warn about missing recommended fields
        if self.data:
            all_keys = set(self.data[0].keys())
            missing_recommended = self.RECOMMENDED_FIELDS - all_keys
            if missing_recommended:
                self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")
        
        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
    
    def save(self, output_dir: str = None, flat: bool = False, **kwargs) -> str:
        """
        Save the sessions.tsv file.
        Overrides parent to always use TSV format.
        """
        return super().save(output_dir=output_dir, flat=flat, file_format="tsv")
