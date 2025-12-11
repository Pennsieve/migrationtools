# Helpers functions

import csv
import io
import os
import re
import json
import string
import requests

from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote
from typing import Literal, Optional

INPUT_FILE_PATH = "input/mastermigration_metadata.csv"

TASK_NAME = "clinical"
IEEG_TASK_DESCRIPTION = "IEEG monitoring for diagnostic clinical purposes, secondary use of clinical data for research purposes"
INSTITUTION_NAME = "Penn Medicine"

POWER_LINE_FREQUENCY = 60

SOFTWARE_FILTERS = "n/a"
MANUFACTURERS_MODEL_NAME = "Quantum"

RECORDING_TYPE = "discontinuous"

SPECIES = "home sapiens"
POPULATION = "adult"

ELECTRODES_SIZE = 2.3
ELECTRODES_MANUFACTURER = "AD-TECH"
ELECTRODES_GROUP = "SEEG"

API_KEY = "eyJraWQiOiJwcjhTaWE2dm9FZTcxNyttOWRiYXRlc3lJZkx6K3lIdDE4RGR5aGVodHZNPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIwNzYyZjdlZS1kZTIwLTRkYzUtODVlMS1iMTQ2NGZhNjE1ZjAiLCJkZXZpY2Vfa2V5IjoidXMtZWFzdC0xXzk4ZTZmMGU2LTU4ZGYtNDkxOS05ZDczLTIwYzE1ZDZmNjIxZCIsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy1lYXN0LTEuYW1hem9uYXdzLmNvbVwvdXMtZWFzdC0xX2IxTnl4WWNyMCIsImNsaWVudF9pZCI6IjY3MG1vN3NpODFwY2Mzc2Z1YjdvMTkxNGQ4Iiwib3JpZ2luX2p0aSI6ImU0NjM0YTJiLWIyMGQtNDI0OS1hMWM3LTk4YjQwZWQzMjk3ZiIsImV2ZW50X2lkIjoiODBkODE3NWItNThiOC00Mzc1LWE1NzgtY2UwYWNhZmYxMzBhIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiIsImF1dGhfdGltZSI6MTc2NTQ4MzIzNywiZXhwIjoxNzY1NDg2ODM3LCJpYXQiOjE3NjU0ODMyMzcsImp0aSI6IjMyYzUzODE2LTNkNmQtNDgwOC04MzcyLTczMGViMTk0NTQ0YyIsInVzZXJuYW1lIjoiMDc2MmY3ZWUtZGUyMC00ZGM1LTg1ZTEtYjE0NjRmYTYxNWYwIn0.bu6yoEzq3CgL7EaUv9_9XmI6lzhEnIvLrDkKpnNQMjbCRVUKCZDkQeZX4bXK7FfdZ1SSyiXuHFreygCs-GOllXMV4jx1QeSGrGa5c9jx40Oeh7U6lA5p_yMA0_7HFk3Lu4mwofWRXJcD7uHmY2AAjGDJDSrGAEKntqqSxg6Cq_YpI0_8vjZsKx54GVzj3Z3IA5IvtjSbTPq7VPWMrFSHGgfz-0qUKYzdoONn4HF8IC4-0vJm0Amr6B7Kpd8hmFCDsIJyRagXiDdzdqf0j8-sEj917PUskb0bXbx0QJYKYRfFHXU0ZeXfNNdxhOVIyPneJTQOdpjI-3QX5TYJij4cMg"
BASE_URL = "https://api.pennsieve.io"
MASTER_CSV_PATH = "input/mastermigration_metadata.csv"
OUTPUT_DIR = "output"
PAGE_SIZE = 25
CACHE_DIR = "cache"

MASTER_MIGRATION_METADATA = "input/mastermigration_metadata.csv"
MASTER_SUBJECT_METADATA = "input/mastersubject_metadata.csv"
PREFIX = "PennEPI"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHANNEL_CONFIGS = {
    "ECG": {
        "names": ["EKG", "EKG1", "EKG2", "ECG", "ECG1", "ECG2"],
        "type": "ECG",
        "group": "n/a",
    },
    "EEG": {
        "names": ["C3", "C03", "C4", "C04", "CZ", "F3", "F4", "F7", "F8", 
                  "FP1", "FP2", "FZ", "O1", "O2", "P3", "P4", "PZ", 
                  "T3", "T4", "T5", "T6"],
        "type": "EEG",
        "group_strategy": "use_name",  # group = channel name
    },
    "EOG": {
        "names": ["LOC", "ROC"],
        "type": "EOG",
        "group_strategy": "use_name",
    },
    "EMG": {
        "names": ["EMG", "EMG1", "EMG2"],
        "type": "EMG",
        "group_strategy": "use_name",
    },
}

# Build reverse lookup once at module load
CHANNEL_LOOKUP = {}
for config_name, config in CHANNEL_CONFIGS.items():
    for channel_name in config["names"]:
        CHANNEL_LOOKUP[channel_name] = {
            "type": config["type"],
            "group": channel_name if config.get("group_strategy") == "use_name" 
                     else config.get("group", "n/a")
        }

def get_channel_info(channel_name: str) -> dict:
    """Get type and group for a channel name."""
    # Handle special cases
    if channel_name.upper() in ["REF", "GND"]:
        return {"type": "unknown", "group": "unknown"}

    # Check if channel matches known configurations
    if channel_name in CHANNEL_LOOKUP:
        return CHANNEL_LOOKUP[channel_name]

    # Default to SEEG with group = first 2 letters of channel name
    # Extract first 2 letters for group
    group = channel_name[:2] if len(channel_name) >= 2 else channel_name
    return {"type": "SEEG", "group": group}

def get_all_datasets():
    """Paginate through all datasets from Pennsieve API."""
    datasets = []
    offset = 0
    headers = {"accept": "*/*"}

    while True:
        url = (
            f"{BASE_URL}/datasets/paginated"
            f"?limit={PAGE_SIZE}&offset={offset}&orderBy=Name&orderDirection=Asc"
            f"&includeBannerUrl=false&includePublishedDataset=false&api_key={API_KEY}"
        )
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        batch = data.get("datasets", [])
        if not batch:
            break

        datasets.extend(batch)
        offset += PAGE_SIZE
        if offset >= data.get("totalCount", 0):
            break

    return datasets

def get_dataset_packages(dataset_id):
    """Return all packages for a dataset, handling pagination."""
    encoded_id = quote(dataset_id, safe="")
    base_url = (
        f"{BASE_URL}/datasets/{encoded_id}/packages?"
        f"pageSize=1000&includeSourceFiles=false&api_key={API_KEY}"
    )
    headers = {"accept": "*/*"}
    
    all_packages = []
    cursor = None
    
    while True:
        url = f"{base_url}&cursor={cursor}" if cursor else base_url
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Assuming packages are in a key like 'packages' or 'items'
        # You'll need to adjust this based on actual response structure
        all_packages.extend(data.get('packages', []))
        
        # Check if there's a next page
        cursor = data.get('cursor')
        if not cursor:
            break
    
    return all_packages

def sanitize_group_name(name: str) -> str:
    """Strip punctuation and spaces from name for group column."""
    return re.sub(r"[^\w]", "", name)

def get_freq_duration(node_id) -> str:
    url = f"https://api.pennsieve.io/packages/download-manifest"

    payload = { "nodeIds": [node_id] }
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    response = requests.post(url, json=payload, headers=headers)
    response_json = response.json()
    data = response_json["data"]
    for payload in data:
        download_url = payload["url"]

    response = requests.get(download_url)
    response.raise_for_status()
    print(node_id)
    ieeg_json =  response.json()

    sampling_frequency = ieeg_json.get("SamplingFrequency","n/a")
    duration = ieeg_json.get("RecordingDuration","n/a")

    return {"sampling_frequency": sampling_frequency, "duration": duration}

def get_electrode_data(node_id: str):
    manifest_url = "https://api.pennsieve.io/packages/download-manifest"

    payload = {"nodeIds": [node_id]}
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    resp = requests.post(f"{manifest_url}?api_key={API_KEY}", json=payload, headers=headers)
    resp.raise_for_status()

    manifest = resp.json()
    data = manifest.get("data", [])
    if not data:
        raise ValueError("No download URLs returned from Pennsieve API.")

    download_url = data[0].get("url")
    if not download_url:
        raise ValueError("Manifest response missing 'url' key.")

    file_resp = requests.get(download_url)
    file_resp.raise_for_status()

    csv_text = file_resp.text
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    return rows

def eps_to_penn_epi(dataset_name: str) -> str:
    """
    Convert dataset name like 'EPS00049' → 'PENNEPI00049'.
    Handles any EPS prefix with variable zeros.
    """
    match = re.search(r"(\d+)", dataset_name)
    num = match.group(1) if match else "00000"
    return f"PennEPI{int(num):05d}"

def penn_epi_to_eps(dataset_name: str) -> str:
    """
    Convert dataset name like 'PennEPI00049' → 'EPS0000049'.
    Extracts numeric portion and formats with 7-digit zero padding.
    """
    match = re.search(r"(\d+)", dataset_name)
    num = match.group(1) if match else "0000000"
    return f"EPS{int(num):07d}"

def clean_channel_name(pkg_name: str) -> str:
    name = pkg_name.lower().removesuffix(".mef")
    name = re.sub(r"(eeg|-ref)", "", name)
    name = name.translate(str.maketrans("", "", string.punctuation))
    return name.strip().upper() 

def save_data(data, name: str):
    """
    Save data (dict, list, etc.) to a JSON file in the cache directory.
    """
    file_path = os.path.join(CACHE_DIR, f"{name}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # print(f"✅ Saved data to {file_path}")


def load_data(name: str, force_reload: bool = False):
    """
    Load cached data if it exists.
    Returns None if the file does not exist or cannot be read.
    Allows empty lists/dicts as valid cached results.

    Args:
        name: The name of the cache file (without extension)
        force_reload: If True, skip cache and return None to force a reload
    """
    if force_reload:
        return None

    file_path = os.path.join(CACHE_DIR, f"{name}.json")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # print(f"📦 Loaded cached data from {file_path}")
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Could not load cache ({e})")
        return None
    

def multi_dataset_read_csv_to_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Reads the master CSV and groups rows by EPS Number and sub-dataset (e.g., D01, D02...).

    If an EPS has only one sub-dataset, that sub-dataset is flattened
    into the root of that EPS entry.
    """
    data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eps = (row.get("EPS Number") or "").strip()
            subdataset = (row.get("Dataset") or "").strip() or "XX"

            if not eps:
                continue  # skip rows with no EPS Number

            # Initialize if needed
            if eps not in data:
                data[eps] = {}

            # store row data under subdataset
            data[eps][subdataset] = {
                k: v for k, v in row.items() if k not in ("EPS Number", "Dataset")
            }

    # post-process: flatten EPS with only one subdataset
    flattened: Dict[str, Dict[str, Any]] = {}
    for eps, subdatasets in data.items():
        if len(subdatasets) == 1:
            # Extract the only subdataset’s dict
            only_key = next(iter(subdatasets))
            flattened[eps] = subdatasets[only_key]
        else:
            flattened[eps] = subdatasets

    return flattened


def read_csv_to_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    data = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eps = row.get("EPS Number")
            if not eps:
                continue  # skip rows with no EPS Number
            data[eps.strip()] = {k: v for k, v in row.items() if k != "EPS Number"}
    return data

def parse_electrode_txt(data):
    def parse_line(line):
        parts = line.split("\t")
        if len(parts) < 6:
            return None
        return {
            "label": parts[0],
            "x": float(parts[1]),
            "y": float(parts[2]),
            "z": float(parts[3]),
            "type": parts[4],
            "group": parts[5]
        }

    parsed = []

    if isinstance(data, str):
        lines = data.strip().splitlines()
        for line in lines:
            item = parse_line(line)
            if item:
                parsed.append(item)

    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                for k, v in entry.items():
                    for line in (k, v):
                        item = parse_line(line)
                        if item:
                            parsed.append(item)
            elif isinstance(entry, str):
                item = parse_line(entry)
                if item:
                    parsed.append(item)

    # Convert list → dict keyed by label
    result = {item["label"]: {k: v for k, v in item.items() if k != "label"} for item in parsed}
    return result

def generate_new_name(old_name: str) -> str:
    """
    Generate a new PennEPI dataset name from an old EPS-style name.

    Examples:
        EPS0000215  → PennEPI00215
        EPS00049    → PennEPI00049
        eps15       → PennEPI00015
        EPS_00123   → PennEPI00123
    """
    old_name = old_name.strip()

    # Normalize case and remove underscores/spaces just in case
    match = re.match(r"(?i)^EPS[_\s]*(\d+)$", old_name)
    if not match:
        # Not an EPS-prefixed name — return unchanged
        return old_name

    # Extract numeric portion and normalize to 5 digits
    numeric_part = match.group(1).lstrip("0") or "0"
    new_suffix = numeric_part.zfill(5)

    return f"PennEPI{new_suffix}"