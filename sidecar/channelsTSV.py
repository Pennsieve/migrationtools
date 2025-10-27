from typing import Dict, Any, List
from .Sidecar import Sidecar


class ChannelsTSV(Sidecar):
    """
    Represents the channels.tsv BIDS sidecar.
    
    TSV format for channel-level metadata.
    Data should be a list of dictionaries, where each dictionary represents a channel row.
    """

    default_filename = "channels.tsv"
    default_bids_path = "bids_root/"

    # All fields are required according to BIDS spec
    REQUIRED_FIELDS = {
        "name",
        "type",
        "units",
        "sampling_frequency"
    }
    
    # Optional but recommended fields
    RECOMMENDED_FIELDS = {
        "low_cutoff",
        "high_cutoff",
        "notch"
    }
    
    OPTIONAL_FIELDS = {
        "reference",
        "status",
        "status_description"
    }

    # For TSV, defaults don't make sense since each row is different
    DEFAULTS = {}

    def __init__(self, fields: List[Dict[str, Any]], **kwargs):
        """
        Initialize ChannelsTSV with a list of channel dictionaries.
        
        Args:
            fields: List of dictionaries, each representing a channel row
                   Example: [
                       {
                           "name": "Fp1",
                           "type": "EEG",
                           "units": "uV",
                           "sampling_frequency": 2000,
                           "low_cutoff": 0,
                           "high_cutoff": 500,
                           "notch": "n/a"
                       },
                       ...
                   ]
        """
        if not isinstance(fields, list):
            raise TypeError("ChannelsTSV requires fields to be a list of dictionaries")
        
        # For TSV sidecars, we store the list directly as data
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
            f"{self.__class__.__name__} initialized with {len(self.data)} channels"
        )

    def validate(self):
        """
        Validate the channels.tsv data structure.
        """
        if not isinstance(self.data, list) or not self.data:
            raise ValueError("ChannelsTSV data must be a non-empty list of dictionaries")
        
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
                raise ValueError(f"Row {i} (channel: {row.get('name', 'unknown')}) missing REQUIRED fields: {sorted(missing_required)}")
        
        # Warn about missing recommended fields
        if self.data:
            all_keys = set(self.data[0].keys())
            missing_recommended = self.RECOMMENDED_FIELDS - all_keys
            if missing_recommended:
                self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")
        
        self.log.info(f"{self.__class__.__name__} validation passed for {len(self.data)} channels.")
        return True
    
    def save(self, output_dir: str = None, flat: bool = False, **kwargs) -> str:
        """
        Save the channels.tsv file.
        Overrides parent to always use TSV format.
        """
        return super().save(output_dir=output_dir, flat=flat, file_format="tsv")
    
    @staticmethod
    def determine_channel_type(channel_name: str) -> str:
        """
        Determine channel type based on channel name.
        
        Args:
            channel_name: Name of the channel (e.g., "Fp1", "EKG1", "EOG1")
        
        Returns:
            str: Channel type ("EEG", "ECG", "EOG", "MISC")
        
        TODO: Enhance this logic as needed for your specific data.
        """
        channel_upper = channel_name.upper()
        
        # ECG channels
        if any(keyword in channel_upper for keyword in ["EKG", "ECG", "CARD"]):
            return "ECG"
        
        # EOG channels
        if any(keyword in channel_upper for keyword in ["EOG", "EYE"]):
            return "EOG"
        
        # EMG channels
        if any(keyword in channel_upper for keyword in ["EMG", "MUSC"]):
            return "EMG"
        
        # Default to EEG for standard EEG electrode names
        # Common EEG electrode names based on 10-20 system
        eeg_patterns = [
            "FP", "F", "C", "P", "O", "T", "A",  # Standard positions
            "Z",  # Midline
        ]
        
        if any(channel_upper.startswith(pattern) or pattern in channel_upper for pattern in eeg_patterns):
            return "EEG"
        
        # If unknown, default to MISC
        return "MISC"
