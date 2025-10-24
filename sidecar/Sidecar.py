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
class Sidecar(ABC):
    """
    Base class for all BIDS sidecar files.
    Handles data management, path handling, validation, and persistence.
    """

    # Exclude these fields from being treated as data fields
    excluded_fields = {"output_dir", "input_dir", "bids_path"}

    default_filename: str = "sidecar.json"
    default_bids_path: str = "bids_root/"

    _logger: Optional[logging.Logger] = None
    _log_dir: str = "output/logs"  

    json_indent: int = 2

    REQUIRED_FIELDS = {}
    RECOMMENDED_FIELDS = {}
    OPTIONAL_FIELDS = {}

    @classmethod
    def configure_logger(cls, log_dir: str):
        """
        Allows user to set a custom log directory before instantiation.
        Example:
            Sidecar.configure_logger("custom_logs/")
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
        with _logger_lock:
            if cls._logger is None:
                cls._logger = setup_logger("sidecar_data_generator", log_dir=cls._log_dir)
                cls._logger.debug(f"Logger initialized for Sidecar (log_dir={cls._log_dir})")
            return cls._logger

    def __init__(self, fields: Dict[str, Any], **kwargs):
        self.log = self.get_logger()

        if not isinstance(fields, dict):
            raise TypeError("fields must be a dictionary")

        path_defaults = {"bids_path": self.default_bids_path}
        merged_paths = {**path_defaults, **kwargs}

        self.paths = {k: v for k, v in merged_paths.items() if k in self.excluded_fields}
        self.data = {k: v for k, v in fields.items() if k not in self.excluded_fields}

        for key, value in self.data.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        self.json_indent = kwargs.pop("json_indent", self.json_indent)

        self.log.debug(f"Initialized {self.__class__.__name__} with {len(self.data)} fields")

    @abstractmethod
    def validate(self):
        """Each sidecar must define its own validation logic."""
        pass

    def to_dict(self):
        return self.data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent)

    def save(self, output_dir: str = None, flat: bool = False, json_indent: Optional[int] = None) -> str:
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