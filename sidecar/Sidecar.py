# Base Class: provides the core infrastructure for all sidecar files.

import os
import sys
import json
import logging
import threading

from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
sys.path.append(str(Path(__file__).resolve().parents[1]))
from logger.setup_logger import setup_logger

_logger_lock = threading.Lock()
class Sidecar(ABC): # ABC = Abstract Base Class
    """
    Base class for all BIDS sidecar files.
    Handles data management, path handling, validation, and persistence.

    Provides common functionalities:
     - __init__() - initialization logic
    - save() - saves JSON to disk
    - to_dict() - converts to dictionary
    - to_json() - converts to JSON string
    - get_logger() - logging setup

    A template that says any subclass must have these features.
    """

    # Exclude these fields from being treated as data fields
    excluded_fields = {"output_dir", "input_dir", "bids_path", "filename"}

    default_filename: str = "sidecar.json"
    default_bids_path: str = "bids_root/"

    _logger: Optional[logging.Logger] = None
    _log_dir: str = "logs/sidecar_logs"

    json_indent: int = 2

    REQUIRED_FIELDS = {}
    RECOMMENDED_FIELDS = {}
    OPTIONAL_FIELDS = {}


    # ==== Class Methods ==== 
    @classmethod
    def configure_logger(cls, log_dir: str):
        """
        Allows user to set a custom log directory before instantiation.
        Example:
            Sidecar.configure_logger("logs/sidecar_logs/")
        """
        cls._log_dir = log_dir
        # If logger already exists, reconfigure it
        if cls._logger:
            for handler in cls._logger.handlers[:]:
                cls._logger.removeHandler(handler)
            cls._logger = setup_logger("sidecar_data_generator", log_dir=cls._log_dir)
            cls._logger.info(f"Logger reconfigured with new log_dir: {log_dir}")

    @classmethod
    def get_logger(cls):
        """
        Returns a logger instance for the Sidecar class.
        Initializes the logger if it hasn't been created yet.
        """
        with _logger_lock:
            if cls._logger is None:
                cls._logger = setup_logger("sidecar_data_generator", log_dir=cls._log_dir)
                cls._logger.debug(f"Logger initialized for Sidecar (log_dir={cls._log_dir})")
            return cls._logger



    # ==== Instance Methods ==== 
    def __init__(self, fields: Dict[str, Any], **kwargs):
        """
        Purpose:
        Get the logger instance
        Initialize Sidecar with given fields and paths.
        Merges user-supplied fields with defaults.
        Separate data into 2 categories:
            - self.paths: contains path-related fields (those in excluded_fields)
            - self.data: contains actual sidecar data (everything from fields)
        Dynamically creates attributes for each data field using setattr()
        Handles optional json_indent parameter 

        Example:
        sidecar = Sidecar(
        fields={"Temperature": 20, "Humidity": 60}, fields you want to modify
        bids_path="sub-01/ses-01/", your specific BIDS path
        output_dir="output/data/" optional, a basic output directory for storing sidecar files
)
        """
        self.log = self.get_logger()

        if not isinstance(fields, dict):
            raise TypeError("fields must be a dictionary")

        path_defaults = {"bids_path": self.default_bids_path}
        merged_paths = {**path_defaults, **kwargs}

        self.paths = {k: v for k, v in merged_paths.items() if k in self.excluded_fields}
        self.data = {k: v for k, v in fields.items() if k not in self.excluded_fields}

        # Handle custom filename if provided
        if "filename" in kwargs:
            self.default_filename = kwargs["filename"]

        for key, value in self.data.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        self.json_indent = kwargs.pop("json_indent", self.json_indent)

        self.log.debug(f"Initialized {self.__class__.__name__} with {len(self.data)} fields")

    @abstractmethod
    def validate(self):
        """Forces subclasses to implement domain-specific validation rules."""
        pass

    def to_dict(self):
        """Returns the sidecar data (self.data) as a dictionary."""
        return self.data

    def to_json(self, indent: int = 2) -> str:
        """Converts the sidecar data to a JSON string."""
        return json.dumps(self.data, indent=indent)
    
    def to_tsv(self) -> str:
        """
        Converts the sidecar data to a TSV string.
        Expects self.data to be a list of dictionaries (rows).
        Returns a TSV formatted string.
        """
        import csv
        import io
        
        if not isinstance(self.data, list) or not self.data:
            raise ValueError("TSV format requires data to be a non-empty list of dictionaries")
        
        output = io.StringIO()
        fieldnames = self.data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(self.data)
        return output.getvalue()

    def save(self, output_dir: str = None, flat: bool = False, json_indent: Optional[int] = None, file_format: str = "json") -> str:
        """
        Saves the sidecar data as a JSON or TSV file to disk.
        
        Args:
            output_dir: Directory to save the file
            flat: If True, save directly under output_dir; if False, use BIDS path structure
            json_indent: Indentation level for JSON (ignored for TSV)
            file_format: "json" or "tsv" (default: "json")
        
        Returns:
            str: Full path to the saved file
        """
        if json_indent is None:
                json_indent = getattr(self, "json_indent", 2)
        
        if not output_dir:
            output_dir = self.paths.get("output_dir", "output/json")

        filename = getattr(self, "default_filename", "sidecar.json")

        if flat:
            file_path = os.path.join(output_dir, filename)
        else:
            bids_path = self.paths.get("bids_path", self.default_bids_path)
            file_path = os.path.join(output_dir, bids_path, filename)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write file based on format
        if file_format == "tsv":
            with open(file_path, "w", newline='', encoding='utf-8') as f:
                f.write(self.to_tsv())
        else:  # default to json
            with open(file_path, "w") as f:
                json.dump(self.data, f, indent=json_indent, default=str)

        self.log.info(f"Saved {self.__class__.__name__} to {file_path}")
        return file_path


    def __repr__(self):
        return f"<{self.__class__.__name__} fields={len(self.data)} paths={self.paths}>"


    def __str__(self):
        return json.dumps(self.data, indent=2)


    def show_field_summary(self, log=False):
        summary = (
            f"REQUIRED: {', '.join(sorted(self.REQUIRED_FIELDS))}\n"
            f"RECOMMENDED: {', '.join(sorted(self.RECOMMENDED_FIELDS))}\n"
            f"OPTIONAL: {', '.join(sorted(self.OPTIONAL_FIELDS))}"
        )
        if log:
            self.log.info(summary)
        else:
            print(summary)