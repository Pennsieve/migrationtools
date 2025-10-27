import os
import sys
import json
import logging
import threading

from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List

sys.path.append(str(Path(__file__).resolve().parents[1]))
from logger.setup_logger import setup_logger


_logger_lock = threading.Lock()


class Sidecar(ABC):
    """
    Base class for all BIDS sidecar files.
    Handles data management, path handling, logging, and persistence.

    Validation is handled separately via `validate()` or `run_validation()`,
    not during save().
    """

    excluded_fields = {"output_dir", "input_dir", "bids_path"}

    default_filename: str = "sidecar.json"
    default_bids_path: str = "bids_root/"
    file_format: str = "json"

    _logger: Optional[logging.Logger] = None
    _log_dir: str = "output/logs"

    json_indent: int = 2

    REQUIRED_FIELDS = {}
    RECOMMENDED_FIELDS = {}
    OPTIONAL_FIELDS = {}

    # ----------------------------------------------------------------------
    # Logging
    # ----------------------------------------------------------------------
    @classmethod
    def configure_logger(cls, log_dir: str):
        """
        Allows user to set a custom log directory before instantiation.
        Example:
            Sidecar.configure_logger("custom_logs/")
        """
        cls._log_dir = log_dir
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

    # ----------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------
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

    # ----------------------------------------------------------------------
    # Validation (abstract)
    # ----------------------------------------------------------------------
    @abstractmethod
    def validate(self, strict: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the current sidecar.

        Returns
        -------
        (bool, dict)
            bool: Whether validation passed
            dict: Structured result containing messages, errors, etc.
        """
        pass

    def run_validation(self, strict: bool = True) -> bool:
        """
        Wrapper that runs validation, logs the results, and optionally raises errors.
        """
        ok, report = self.validate(strict=strict)
        if not ok:
            for msg in report.get("errors", []):
                self.log.error(msg)
            for msg in report.get("warnings", []):
                self.log.warning(msg)
            if strict:
                raise ValueError(f"Validation failed for {self.__class__.__name__}")
        else:
            self.log.info(f"{self.__class__.__name__} validation passed.")
        return ok

    def save(
        self,
        **kwargs
    ) -> str:
        """
        Save sidecar to disk. Caller must provide data explicitly.
        """
        data = kwargs.get("data", self.data)
        
        if kwargs.get("validate", False):
            ok, report = self.validate(data)
            if not ok:
                self.log.warning(
                    f"Validation failed with {len(report.get('errors', []))} errors"
                )

        output_dir = kwargs.get("output_dir", None) or "output/json"
        filename = self.default_filename
        file_path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Actual writing handled by subclass or format writer
        self.write_data(file_path, data)

        self.log.info(f"Saved {self.__class__.__name__} to {file_path}")
        return file_path

    def write_data(self, file_path: str, data: Dict[str, Any]):
        """Default JSON writer."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=self.json_indent, default=str)

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
