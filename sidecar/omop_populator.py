#!/usr/bin/env python3
"""
OMOP Record Populator

Populates OMOP-style models from BIDS data files across Pennsieve datasets.

Data is extracted from multiple source files (participants.tsv, sessions.tsv, *_ieeg.json)
and combined based on participant_id to create records for each model.

Usage:
  # Dry run for specific datasets
  python omop_populator.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00089 PennEPI00090 \\
      --models person eeg --dry-run

  # Process all PennEPI datasets for all models
  python omop_populator.py --api-key KEY --api-secret SECRET \\
      --prefix PennEPI --models all

  # Process specific model with template ID
  python omop_populator.py --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00089 \\
      --models person --template-id UUID_HERE

  # Force reload data from network (bypass cache)
  python omop_populator.py --api-key KEY --api-secret SECRET \\
      --prefix PennEPI --models person --force-reload
"""

import argparse
import csv
import fnmatch
import io
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote

import requests
import boto3

from helpers import (
    load_data,
    save_data,
    BASE_URL,
)

API2_BASE_URL = "https://api2.pennsieve.io"
SCRIPT_DIR = Path(__file__).parent
DEFAULT_MAPPINGS_FILE = SCRIPT_DIR / "schemas" / "omop_mappings_v2.json"


class AuthenticationClient:
    """Handles Pennsieve authentication via Cognito."""

    def __init__(self, api_host: str = BASE_URL):
        self.api_host = api_host
        self._access_token: Optional[str] = None

    def authenticate(self, api_key: str, api_secret: str) -> str:
        """Authenticate and return access token."""
        url = f"{self.api_host}/authentication/cognito-config"

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        cognito_app_client_id = data["tokenPool"]["appClientId"]
        cognito_region = data["region"]

        cognito_idp_client = boto3.client(
            "cognito-idp",
            region_name=cognito_region,
            aws_access_key_id="",
            aws_secret_access_key="",
        )

        login_response = cognito_idp_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": api_key, "PASSWORD": api_secret},
            ClientId=cognito_app_client_id,
        )

        self._access_token = login_response["AuthenticationResult"]["AccessToken"]
        return self._access_token

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    def get_auth_headers(self) -> Dict[str, str]:
        """Return headers with Bearer token for authenticated requests."""
        if not self._access_token:
            raise ValueError("Not authenticated. Call authenticate() first.")
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }


class OMOPPopulator:
    """Populates OMOP models from BIDS data files."""

    def __init__(
        self,
        auth_client: AuthenticationClient,
        dry_run: bool = False,
        force_reload: bool = False,
        verbose: bool = False,
        mappings_file: Optional[Path] = None
    ):
        self.auth_client = auth_client
        self.dry_run = dry_run
        self.force_reload = force_reload
        self.verbose = verbose
        self.mappings_file = mappings_file or DEFAULT_MAPPINGS_FILE
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict:
        """Load field mappings from config file."""
        with open(self.mappings_file) as f:
            return json.load(f)

    def _log(self, message: str, indent: int = 0):
        """Print log message with optional indentation."""
        prefix = "  " * indent
        print(f"{prefix}{message}")

    def _debug(self, message: str, indent: int = 0):
        """Print debug message if verbose mode is on."""
        if self.verbose:
            self._log(f"[DEBUG] {message}", indent)

    def _normalize_value(self, field_name: str, value: Any) -> Any:
        """
        Apply data normalizations and fixes for known issues.

        Handles:
        - species typos ("homo sapien" -> "homo sapiens")
        - site_code padding ("5" -> "005")
        - sex/gender n/a values -> None
        - other field-specific transformations
        """
        if value is None:
            return None

        # Species fixes
        if field_name == "species" and isinstance(value, str):
            # Fix common typos
            if value.lower() in ("homo sapien", "home sapiens", "home sapien"):
                return "homo sapiens"

        # Site code padding (e.g., "5" -> "005")
        if field_name == "site_code" and isinstance(value, str):
            # Pad to 3 digits if it's a number
            if value.isdigit():
                return value.zfill(3)

        # Sex/gender - convert n/a to None (schema expects enum or null)
        if field_name in ("sex", "gender") and isinstance(value, str):
            if value.lower() in ("n/a", "na", "unknown", ""):
                return None

        # Generic n/a handling for enum fields that don't accept n/a
        # (variant_pathogenicity, zygosity, etc. - these accept null but not "n/a" unless in enum)
        if field_name in ("variant_pathogenicity", "zygosity") and isinstance(value, str):
            if value.lower() in ("n/a", "na", ""):
                return None

        return value

    # -------------------------------------------------------------------------
    # Dataset and Package Helpers
    # -------------------------------------------------------------------------

    def get_all_datasets(self) -> List[Dict]:
        """Get all datasets, with caching."""
        datasets = load_data("datasets", force_reload=self.force_reload)
        if datasets is None:
            self._log("Fetching datasets from network...")
            datasets = self._fetch_all_datasets()
            save_data(datasets, "datasets")
        return datasets

    def _fetch_all_datasets(self) -> List[Dict]:
        """Paginate through all datasets from Pennsieve API."""
        datasets = []
        offset = 0
        page_size = 25

        while True:
            url = (
                f"{BASE_URL}/datasets/paginated"
                f"?limit={page_size}&offset={offset}&orderBy=Name&orderDirection=Asc"
                f"&includeBannerUrl=false&includePublishedDataset=false"
            )
            response = requests.get(url, headers=self.auth_client.get_auth_headers())
            response.raise_for_status()
            data = response.json()

            batch = data.get("datasets", [])
            if not batch:
                break

            datasets.extend(batch)
            offset += page_size
            if offset >= data.get("totalCount", 0):
                break

        return datasets

    def get_dataset_packages(self, dataset_id: str, dataset_name: str) -> List[Dict]:
        """Get all packages for a dataset, with caching."""
        cache_key = f"package_{dataset_name}"
        packages = load_data(cache_key, force_reload=self.force_reload)
        if packages is None:
            self._log("Fetching packages from network...", indent=1)
            packages = self._fetch_dataset_packages(dataset_id)
            save_data(packages, cache_key)
        return packages

    def _fetch_dataset_packages(self, dataset_id: str) -> List[Dict]:
        """Fetch all packages for a dataset using pagination."""
        encoded_id = quote(dataset_id, safe="")
        base_url = f"{BASE_URL}/datasets/{encoded_id}/packages?pageSize=1000&includeSourceFiles=false"

        all_packages = []
        cursor = None

        while True:
            url = f"{base_url}&cursor={cursor}" if cursor else base_url
            response = requests.get(url, headers=self.auth_client.get_auth_headers())
            response.raise_for_status()

            data = response.json()
            all_packages.extend(data.get('packages', []))

            cursor = data.get('cursor')
            if not cursor:
                break

        return all_packages

    def find_dataset_by_name(self, name: str, all_datasets: List[Dict]) -> Optional[Dict]:
        """Find a dataset by name."""
        for ds in all_datasets:
            content = ds.get("content", {})
            if content.get("name", "").strip() == name:
                return ds
        return None

    def get_package_path(self, package: Dict, all_packages: List[Dict]) -> str:
        """Reconstruct the path to a package by walking up parent IDs."""
        pkg_lookup = {}
        for pkg in all_packages:
            content = pkg.get("content", {})
            pkg_id = content.get("id")
            if pkg_id:
                pkg_lookup[pkg_id] = pkg

        path_parts = []
        current = package

        while True:
            content = current.get("content", {})
            parent_id = content.get("parentId")

            if not parent_id or parent_id not in pkg_lookup:
                break

            parent = pkg_lookup[parent_id]
            parent_content = parent.get("content", {})
            parent_name = parent_content.get("name", "")

            if parent_name:
                path_parts.insert(0, parent_name)

            current = parent

        return "/".join(path_parts)

    # -------------------------------------------------------------------------
    # File Finding and Downloading
    # -------------------------------------------------------------------------

    def find_file(self, packages: List[Dict], pattern: str) -> Optional[Dict]:
        """
        Find a file package matching a pattern.

        Pattern can be exact name or glob pattern (e.g., '*_ieeg.json').
        Skips __DELETED__ files and files in archive folders.
        """
        for pkg in packages:
            content = pkg.get("content", {})
            name = content.get("name", "")
            pkg_type = content.get("packageType", "")

            # Skip collections
            if pkg_type == "Collection":
                continue

            # Skip deleted files
            if name.startswith("__DELETED__"):
                continue

            # Skip files in archive folders
            pkg_path = self.get_package_path(pkg, packages)
            if "archive" in pkg_path.lower():
                continue

            # Match exact name or glob pattern
            if name == pattern or fnmatch.fnmatch(name, pattern):
                return pkg

        return None

    def find_all_files(self, packages: List[Dict], pattern: str) -> List[Dict]:
        """
        Find all file packages matching a pattern.

        Returns list of matching packages. Skips __DELETED__ and archive files.
        """
        matches = []
        for pkg in packages:
            content = pkg.get("content", {})
            name = content.get("name", "")
            pkg_type = content.get("packageType", "")

            if pkg_type == "Collection":
                continue
            if name.startswith("__DELETED__"):
                continue

            pkg_path = self.get_package_path(pkg, packages)
            if "archive" in pkg_path.lower():
                continue

            if name == pattern or fnmatch.fnmatch(name, pattern):
                matches.append(pkg)

        return matches

    def download_file_content(self, node_id: str) -> str:
        """Download file content from Pennsieve.

        Tries the download-manifest endpoint first. If that fails (400),
        falls back to re-fetching the package with source files included
        and downloading via the source file URL.
        """
        # Try download-manifest first
        manifest_url = f"{BASE_URL}/packages/download-manifest"
        payload = {"nodeIds": [node_id]}

        response = requests.post(
            manifest_url,
            json=payload,
            headers=self.auth_client.get_auth_headers()
        )

        if response.ok:
            manifest = response.json()
            data = manifest.get("data", [])
            if data and data[0].get("url"):
                file_response = requests.get(data[0]["url"])
                file_response.raise_for_status()
                return file_response.text

        # Fallback: fetch the package directly with source files included
        self._debug(
            f"download-manifest failed for {node_id} ({response.status_code}), "
            f"trying package source files fallback",
            indent=3,
        )
        pkg_url = f"{BASE_URL}/packages/{node_id}?includeSourceFiles=true"
        pkg_response = requests.get(pkg_url, headers=self.auth_client.get_auth_headers())
        pkg_response.raise_for_status()

        pkg_data = pkg_response.json()
        # Source files may be under "objects" or "sourceFiles"
        sources = pkg_data.get("objects", []) or pkg_data.get("sourceFiles", [])
        if not sources:
            raise ValueError(
                f"download-manifest returned {response.status_code} and package "
                f"{node_id} has no source files to fall back on"
            )

        # Each source file object should have a content.s3key or content.s3Key
        for src in sources:
            content = src.get("content", {})
            s3_key = content.get("s3key") or content.get("s3Key")
            s3_bucket = content.get("s3bucket") or content.get("s3Bucket")
            if s3_key and s3_bucket:
                self._debug(f"Downloading via S3: s3://{s3_bucket}/{s3_key}", indent=3)
                s3_client = boto3.client("s3")
                obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
                return obj["Body"].read().decode("utf-8")

        # If no S3 info, look for a direct URL
        for src in sources:
            url = src.get("url") or src.get("content", {}).get("url")
            if url:
                self._debug(f"Downloading via source URL", indent=3)
                file_response = requests.get(url)
                file_response.raise_for_status()
                return file_response.text

        raise ValueError(
            f"download-manifest returned {response.status_code} and could not "
            f"extract download URL from package {node_id} source files"
        )

    # -------------------------------------------------------------------------
    # Data Extraction
    # -------------------------------------------------------------------------

    def parse_tsv(self, content: str) -> List[Dict[str, Any]]:
        """Parse TSV content into list of dicts."""
        dialect = csv.Sniffer().sniff(content[:1024], delimiters=',\t')
        reader = csv.DictReader(io.StringIO(content), dialect=dialect)
        return list(reader)

    def parse_json(self, content: str) -> Any:
        """Parse JSON content."""
        return json.loads(content)

    def extract_source_data(
        self,
        packages: List[Dict],
        dataset_name: str
    ) -> Dict[str, Any]:
        """
        Extract data from all source files in the dataset.

        Returns dict with:
            - participants: List of participant records (from participants.tsv)
            - sessions: List of session records (from sessions.tsv)
            - ieeg_files: Dict of filename -> ieeg.json content
        """
        source_data = {
            "participants": [],
            "sessions": [],
            "ieeg_files": {},
            "participant_id": None  # Will be set from participants.tsv
        }

        # Find and parse participants.tsv
        participants_pkg = self.find_file(packages, "participants.tsv")
        if participants_pkg:
            node_id = participants_pkg["content"]["nodeId"]
            self._debug(f"Found participants.tsv (node: {node_id})", indent=2)
            try:
                content = self.download_file_content(node_id)
                source_data["participants"] = self.parse_tsv(content)
                if source_data["participants"]:
                    # Get participant_id from first record
                    source_data["participant_id"] = source_data["participants"][0].get("participant_id")
                self._log(f"Loaded {len(source_data['participants'])} participant records", indent=2)
            except Exception as e:
                self._log(f"WARNING: Failed to load participants.tsv: {e}", indent=2)
        else:
            self._log("WARNING: participants.tsv not found", indent=2)

        # Find and parse sessions.tsv
        sessions_pattern = f"*_sessions.tsv"
        sessions_pkg = self.find_file(packages, sessions_pattern)
        if not sessions_pkg:
            # Try exact name
            sessions_pkg = self.find_file(packages, "sessions.tsv")
        if sessions_pkg:
            node_id = sessions_pkg["content"]["nodeId"]
            self._debug(f"Found sessions file (node: {node_id})", indent=2)
            try:
                content = self.download_file_content(node_id)
                source_data["sessions"] = self.parse_tsv(content)
                self._log(f"Loaded {len(source_data['sessions'])} session records", indent=2)
            except Exception as e:
                self._log(f"WARNING: Failed to load sessions: {e}", indent=2)
        else:
            self._debug("sessions.tsv not found", indent=2)

        # Find and parse all *_ieeg.json files
        ieeg_files = self.find_all_files(packages, "*_ieeg.json")
        for pkg in ieeg_files:
            name = pkg["content"]["name"]
            node_id = pkg["content"]["nodeId"]
            pkg_path = self.get_package_path(pkg, packages)
            full_path = f"{pkg_path}/{name}" if pkg_path else name

            self._debug(f"Found ieeg file: {name}", indent=2)
            try:
                content = self.download_file_content(node_id)
                ieeg_data = self.parse_json(content)
                ieeg_data["_file_path"] = full_path  # Store path for file_uri
                ieeg_data["_filename"] = name
                source_data["ieeg_files"][name] = ieeg_data
            except Exception as e:
                self._log(f"WARNING: Failed to load {name}: {e}", indent=2)

        self._log(f"Loaded {len(source_data['ieeg_files'])} ieeg.json files", indent=2)

        return source_data

    # -------------------------------------------------------------------------
    # Record Building
    # -------------------------------------------------------------------------

    def get_session_data(self, sessions: List[Dict], session_id: str) -> Optional[Dict]:
        """Get session record matching session_id."""
        for sess in sessions:
            if sess.get("session_id") == session_id:
                return sess
        return None

    def build_record(
        self,
        model_name: str,
        source_data: Dict[str, Any],
        ieeg_file_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build a single record for a model from source data.

        Args:
            model_name: Name of the model (e.g., 'person', 'eeg')
            source_data: Extracted source data from files
            ieeg_file_data: Optional specific ieeg.json data (for eeg_recording_parameters)

        Returns:
            Record dict or None if required data is missing
        """
        model_config = self.mappings["models"].get(model_name)
        if not model_config:
            self._log(f"ERROR: Unknown model: {model_name}")
            return None

        fields_config = model_config.get("fields", {})
        record = {}

        # Get participant data (first record from participants.tsv)
        participant_data = source_data["participants"][0] if source_data["participants"] else {}

        # Get session data based on model's session filter
        sessions = source_data["sessions"]

        # Track which fields have data from actual sources (not static/person_id)
        has_source_data = set()

        for field_name, field_config in fields_config.items():
            value = None
            is_static = False

            # Handle static values
            if "static_value" in field_config:
                value = field_config["static_value"]
                is_static = True

            # Handle derived values
            elif "derived" in field_config:
                if field_config["derived"] == "package_path" and ieeg_file_data:
                    value = ieeg_file_data.get("_file_path", "")

            # Handle source file lookups
            elif "source_file" in field_config:
                source_file = field_config["source_file"]
                source_column = field_config.get("source_column", field_name)

                if source_file == "participants.tsv":
                    value = participant_data.get(source_column)

                elif "sessions.tsv" in source_file:
                    # Check for session filter
                    filter_config = field_config.get("filter", {})
                    if filter_config:
                        session_id = filter_config.get("session_id")
                        session_data = self.get_session_data(sessions, session_id)
                        if session_data:
                            value = session_data.get(source_column)
                    else:
                        # Use first session if no filter
                        if sessions:
                            value = sessions[0].get(source_column)

                elif "*_ieeg.json" in source_file:
                    if ieeg_file_data:
                        value = ieeg_file_data.get(source_column)
                    else:
                        # Use first ieeg file
                        first_ieeg = list(source_data["ieeg_files"].values())[0] if source_data["ieeg_files"] else {}
                        value = first_ieeg.get(source_column)

            # Apply transforms
            if value is not None:
                # Convert empty strings to None for nullable fields
                if isinstance(value, str) and value.strip() == "":
                    value = None

                if value is not None:
                    transform = field_config.get("transform")
                    if transform == "enum_map" and isinstance(value, str):
                        enum_map = field_config.get("enum_map", {})
                        mapped = enum_map.get(value.lower())
                        if mapped is not None:
                            value = mapped
                        else:
                            self._debug(f"WARNING: '{value}' not in enum_map for {field_name}, passing as-is", indent=3)
                    elif transform == "lowercase" and isinstance(value, str):
                        value = value.lower()
                    elif transform == "split_to_array" and isinstance(value, str):
                        value = [v.strip() for v in value.split(",") if v.strip()]
                    elif transform == "stringify" and not isinstance(value, str):
                        value = json.dumps(value)
                    elif transform == "hardware_filters" and isinstance(value, dict):
                        # Convert {"filter": {"min (Hz)": X, "max (Hz)": Y}}
                        # to     {"filter": {"min": X, "max": Y}}
                        converted = {}
                        for fname, fvals in value.items():
                            if isinstance(fvals, dict):
                                new_vals = {}
                                for k, v in fvals.items():
                                    clean_key = k.replace(" (Hz)", "")
                                    try:
                                        new_vals[clean_key] = float(v)
                                    except (ValueError, TypeError):
                                        new_vals[clean_key] = v
                                converted[fname] = new_vals
                            else:
                                converted[fname] = fvals
                        value = converted
                    elif transform == "software_filters":
                        # Schema expects object with string values
                        if isinstance(value, str):
                            value = {"status": value}
                        elif not isinstance(value, dict):
                            value = {"status": "n/a"}

                    # Type conversion
                    field_type = field_config.get("type")
                    if field_type == "number" and value is not None:
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            value = None
                    elif field_type == "integer" and value is not None:
                        try:
                            value = int(float(value))
                        except (ValueError, TypeError):
                            value = None
                    elif field_type == "string" and value is not None:
                        if isinstance(value, bool):
                            value = str(value).lower()
                        elif isinstance(value, float) and value.is_integer():
                            value = str(int(value))
                        else:
                            value = str(value)

                    # Apply data fixes/normalizations
                    value = self._normalize_value(field_name, value)

            # Only add non-None values (except for required person_id)
            if value is not None or field_name == "person_id":
                record[field_name] = value
                # Track fields that have actual source data (not static, not person_id)
                if value is not None and not is_static and field_name != "person_id":
                    has_source_data.add(field_name)

        # Validate required field
        if not record.get("person_id"):
            self._debug(f"Skipping record - missing person_id", indent=3)
            return None

        # Skip records that have no actual source data beyond person_id and static values
        if not has_source_data:
            self._debug(f"Skipping record - only static values and person_id, no source data", indent=3)
            return None

        return record

    def build_records_for_model(
        self,
        model_name: str,
        source_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build all records for a model.

        Most models produce a single record per dataset.
        eeg_recording_parameters produces one record per ieeg.json file.
        """
        model_config = self.mappings["models"].get(model_name, {})
        records = []

        if model_config.get("multi_record"):
            # Create one record per ieeg.json file
            for filename, ieeg_data in source_data["ieeg_files"].items():
                record = self.build_record(model_name, source_data, ieeg_file_data=ieeg_data)
                if record:
                    records.append(record)
        else:
            # Single record per dataset
            record = self.build_record(model_name, source_data)
            if record:
                records.append(record)

        return records

    # -------------------------------------------------------------------------
    # Model Creation and Record Posting
    # -------------------------------------------------------------------------

    def get_existing_model_by_name(self, dataset_id: str, model_name: str) -> Optional[str]:
        """Find existing model by name in a dataset."""
        encoded_dataset_id = quote(dataset_id, safe="")
        url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded_dataset_id}"

        response = requests.get(url, headers=self.auth_client.get_auth_headers())
        response.raise_for_status()

        models = response.json()
        for item in models:
            model = item.get("model", {})
            if model.get("name") == model_name:
                return model.get("id")

        return None

    def create_model_from_template(
        self,
        template_id: str,
        dataset_id: str,
        model_name: str,
        display_name: str,
        description: str = "",
    ) -> Optional[str]:
        """Create a model from template, or return existing model ID.

        Omitting the version parameter uses the latest template version.
        Omitting description falls back to the template's description.
        """
        encoded_dataset_id = quote(dataset_id, safe="")
        url = (
            f"{API2_BASE_URL}/metadata/templates/{template_id}/models"
            f"?dataset_id={encoded_dataset_id}"
        )
        payload = {
            "name": model_name,
            "display_name": display_name,
        }
        if description:
            payload["description"] = description

        self._debug(f"Creating model: {model_name}", indent=2)
        self._debug(f"URL: {url}", indent=3)

        if self.dry_run:
            self._log(f"[DRY-RUN] Would create model: {model_name}", indent=2)
            return "dry-run-model-id"

        response = requests.post(url, json=payload, headers=self.auth_client.get_auth_headers())

        # Handle duplicate model name
        if response.status_code == 400:
            try:
                error_body = response.json()
                if "duplicate model name" in error_body.get("message", ""):
                    self._log(f"Model '{model_name}' already exists, finding ID...", indent=2)
                    existing_id = self.get_existing_model_by_name(dataset_id, model_name)
                    if existing_id:
                        self._log(f"Found existing model (ID: {existing_id})", indent=2)
                        return existing_id
            except json.JSONDecodeError:
                pass

        if not response.ok:
            self._log(f"ERROR creating model: {response.status_code}", indent=2)
            self._log(f"Response: {response.text}", indent=3)
            response.raise_for_status()

        result = response.json()
        model_id = result.get("model", {}).get("id")

        if model_id:
            self._log(f"Created model (ID: {model_id})", indent=2)

        return model_id

    def post_records(
        self,
        model_id: str,
        records: List[Dict],
        dataset_id: str
    ) -> bool:
        """Post records to a model."""
        encoded_dataset_id = quote(dataset_id, safe="")
        url = f"{API2_BASE_URL}/metadata/models/{model_id}/records?dataset_id={encoded_dataset_id}"
        payload = {"records": records}

        self._debug(f"Posting {len(records)} records", indent=2)
        self._debug(f"URL: {url}", indent=3)
        if self.verbose:
            self._debug(f"Payload: {json.dumps(payload, indent=2)[:500]}...", indent=3)

        if self.dry_run:
            self._log(f"[DRY-RUN] Would post {len(records)} records", indent=2)
            for i, rec in enumerate(records[:3]):
                self._log(f"  Record {i+1}: {json.dumps(rec)[:100]}...", indent=3)
            if len(records) > 3:
                self._log(f"  ... and {len(records) - 3} more", indent=3)
            return True

        response = requests.post(url, json=payload, headers=self.auth_client.get_auth_headers())

        if not response.ok:
            self._log(f"ERROR posting records: {response.status_code}", indent=2)
            self._log(f"Response: {response.text}", indent=3)
            return False

        self._log(f"Posted {len(records)} records successfully", indent=2)
        return True

    # -------------------------------------------------------------------------
    # Main Processing
    # -------------------------------------------------------------------------

    def process_dataset(
        self,
        dataset_name: str,
        all_datasets: List[Dict],
        model_names: List[str],
        template_ids: Dict[str, str]
    ) -> Tuple[int, int]:
        """
        Process a single dataset for all specified models.

        Returns:
            Tuple of (success_count, failure_count, skipped_count)
        """
        self._log(f"\n{'='*60}")
        self._log(f"Processing dataset: {dataset_name}")
        self._log(f"{'='*60}")

        # Find dataset
        dataset = self.find_dataset_by_name(dataset_name, all_datasets)
        if not dataset:
            self._log(f"ERROR: Dataset not found: {dataset_name}", indent=1)
            return (0, len(model_names), 0)

        dataset_id = dataset.get("content", {}).get("id")
        if not dataset_id:
            self._log(f"ERROR: Could not get dataset ID", indent=1)
            return (0, len(model_names), 0)

        self._log(f"Dataset ID: {dataset_id}", indent=1)

        # Get packages
        packages = self.get_dataset_packages(dataset_id, dataset_name)
        self._log(f"Found {len(packages)} packages", indent=1)

        # Extract source data
        self._log("Extracting source data...", indent=1)
        source_data = self.extract_source_data(packages, dataset_name)

        if not source_data["participant_id"]:
            self._log("SKIPPING: No participants.tsv found or no participant_id in data", indent=1)
            return (0, 0, 0)  # Not a failure, just nothing to process

        self._log(f"Participant ID: {source_data['participant_id']}", indent=1)

        success_count = 0
        failure_count = 0
        skipped_count = 0

        for model_name in model_names:
            self._log(f"\n  --- Model: {model_name} ---", indent=1)

            model_config = self.mappings["models"].get(model_name)
            if not model_config:
                self._log(f"ERROR: Unknown model '{model_name}'", indent=2)
                failure_count += 1
                continue

            # Get template ID (only needed if model doesn't already exist)
            template_id = template_ids.get(model_name) or model_config.get("template_id")

            # Check if this is an unstable template
            is_unstable = model_config.get("unstable", False)
            if is_unstable:
                self._log(f"WARNING: '{model_name}' template is marked as unstable - errors may occur", indent=2)

            # Build records
            records = self.build_records_for_model(model_name, source_data)
            if not records:
                self._log(f"SKIPPING: No data available for {model_name}", indent=2)
                skipped_count += 1
                continue

            self._log(f"Built {len(records)} records", indent=2)

            # Resolve the actual model name on Pennsieve (may differ from mapping key)
            pennsieve_model_name = model_config.get("model_name", model_name)
            description = model_config.get("description", "")

            # Display name from mappings, fallback to title-cased model_name
            display_name = model_config.get("display_name") or pennsieve_model_name.replace("_", " ").title()

            try:
                # Find existing model first, only create from template if not found
                model_id = self.get_existing_model_by_name(dataset_id, pennsieve_model_name)
                if model_id:
                    self._log(f"Found existing model '{pennsieve_model_name}' (ID: {model_id})", indent=2)
                else:
                    if not template_id:
                        self._log(f"ERROR: Model '{pennsieve_model_name}' not found and no template_id to create it", indent=2)
                        failure_count += 1
                        continue
                    self._log(f"Model '{pennsieve_model_name}' not found, creating from template...", indent=2)
                    model_id = self.create_model_from_template(
                        template_id=template_id,
                        dataset_id=dataset_id,
                        model_name=pennsieve_model_name,
                        display_name=display_name,
                        description=description
                    )

                if not model_id:
                    self._log(f"ERROR: Failed to create/find model", indent=2)
                    failure_count += 1
                    continue

                # Post records
                if self.post_records(model_id, records, dataset_id):
                    success_count += 1
                else:
                    failure_count += 1

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else "unknown"
                self._log(f"ERROR: HTTP {status_code} - {e}", indent=2)
                if is_unstable:
                    self._log(f"NOTE: This template is unstable, continuing with other models...", indent=2)
                failure_count += 1

            except Exception as e:
                self._log(f"ERROR: {e}", indent=2)
                if is_unstable:
                    self._log(f"NOTE: This template is unstable, continuing with other models...", indent=2)
                failure_count += 1

        return (success_count, failure_count, skipped_count)

    def run(
        self,
        dataset_names: Optional[List[str]] = None,
        dataset_prefix: Optional[str] = None,
        model_names: List[str] = None,
        template_ids: Dict[str, str] = None
    ) -> Tuple[int, int, int]:
        """
        Main entry point for processing.

        Args:
            dataset_names: Explicit list of dataset names
            dataset_prefix: Prefix to match dataset names
            model_names: List of model names to process (or ['all'])
            template_ids: Dict mapping model names to template IDs

        Returns:
            Tuple of (datasets_processed, total_success, total_failures)
        """
        if not dataset_names and not dataset_prefix:
            raise ValueError("Must provide either dataset_names or dataset_prefix")

        template_ids = template_ids or {}

        # Resolve 'all' models
        if model_names == ["all"]:
            model_names = list(self.mappings["models"].keys())

        self._log("="*60)
        self._log("OMOP RECORD POPULATOR")
        self._log("="*60)
        self._log(f"Models: {model_names}")
        self._log(f"Dry run: {self.dry_run}")
        self._log(f"Force reload: {self.force_reload}")
        self._log("="*60)

        # Get all datasets
        all_datasets = self.get_all_datasets()
        self._log(f"Total datasets available: {len(all_datasets)}")

        # Filter datasets
        datasets_to_process = []
        for ds in all_datasets:
            ds_name = ds.get("content", {}).get("name", "")
            if dataset_names and ds_name in dataset_names:
                datasets_to_process.append(ds_name)
            elif dataset_prefix and ds_name.startswith(dataset_prefix):
                datasets_to_process.append(ds_name)

        if not datasets_to_process:
            self._log("No datasets matched the criteria")
            return (0, 0, 0)

        self._log(f"Datasets to process: {len(datasets_to_process)}")

        total_success = 0
        total_failures = 0
        total_skipped = 0

        for ds_name in datasets_to_process:
            success, failures, skipped = self.process_dataset(
                ds_name, all_datasets, model_names, template_ids
            )
            total_success += success
            total_failures += failures
            total_skipped += skipped

        # Summary
        self._log(f"\n{'='*60}")
        self._log("SUMMARY")
        self._log(f"{'='*60}")
        self._log(f"Datasets processed: {len(datasets_to_process)}")
        self._log(f"Model operations succeeded: {total_success}")
        self._log(f"Model operations skipped: {total_skipped}")
        self._log(f"Model operations failed: {total_failures}")

        if self.dry_run:
            self._log("\n[DRY-RUN MODE] No actual changes were made")

        return (len(datasets_to_process), total_success, total_failures)


def main():
    parser = argparse.ArgumentParser(
        description='Populate OMOP models from BIDS data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run for specific datasets and models
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00089 PennEPI00090 \\
      --models person eeg --dry-run

  # Process all PennEPI datasets for all models
  %(prog)s --api-key KEY --api-secret SECRET \\
      --prefix PennEPI --models all

  # Specify template IDs
  %(prog)s --api-key KEY --api-secret SECRET \\
      --datasets PennEPI00089 \\
      --models person \\
      --template-ids person=UUID1 eeg=UUID2
        """
    )

    # Authentication
    parser.add_argument('--api-key', required=True, help='Pennsieve API key')
    parser.add_argument('--api-secret', required=True, help='Pennsieve API secret')

    # Dataset selection
    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        '--datasets', nargs='+', metavar='NAME',
        help='Explicit list of dataset names'
    )
    dataset_group.add_argument(
        '--prefix', metavar='PREFIX',
        help='Process datasets starting with this prefix'
    )

    # Model selection
    parser.add_argument(
        '--models', nargs='+', required=True,
        metavar='MODEL',
        help='Models to process (person, eeg, mri, intervention, fivesense, eeg_recording_parameters, or "all")'
    )

    # Template IDs
    parser.add_argument(
        '--template-ids', nargs='+', metavar='MODEL=UUID',
        help='Template IDs in format: model_name=template_uuid'
    )

    # Options
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--force-reload', action='store_true', help='Bypass cache')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--mappings', metavar='FILE', help='Path to mappings JSON file (default: schemas/omop_mappings_v2.json)')

    args = parser.parse_args()

    # Parse template IDs
    template_ids = {}
    if args.template_ids:
        for item in args.template_ids:
            if '=' in item:
                model, uuid = item.split('=', 1)
                template_ids[model] = uuid

    # Authenticate
    print("Authenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")

    # Resolve mappings file
    mappings_file = Path(args.mappings) if args.mappings else None
    if mappings_file:
        print(f"Using mappings file: {mappings_file}")

    # Create populator and run
    populator = OMOPPopulator(
        auth_client=auth_client,
        dry_run=args.dry_run,
        force_reload=args.force_reload,
        verbose=args.verbose,
        mappings_file=mappings_file
    )

    datasets_processed, success, failures = populator.run(
        dataset_names=args.datasets,
        dataset_prefix=args.prefix,
        model_names=args.models,
        template_ids=template_ids
    )

    # Exit code
    if failures > 0:
        sys.exit(1)
    if datasets_processed == 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
