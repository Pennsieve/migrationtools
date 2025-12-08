# Helpers functions
import csv
import io
import os
import re
import string
import requests

from urllib.parse import quote
from pathlib import Path


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

API_KEY = os.getenv("PENNSIEVE_API_KEY")
BASE_URL = "https://api.pennsieve.io"
MASTER_CSV_PATH = "input/mastermigration_metadata.csv"
OUTPUT_DIR = "output"
PAGE_SIZE = 25
IEEG_JSON_PATH = "output/bids"

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
    """Return all packages for a dataset."""
    encoded_id = quote(dataset_id, safe="")
    url = (
        f"{BASE_URL}/datasets/{encoded_id}/packages?"
        f"pageSize=1000&includeSourceFiles=false&api_key={API_KEY}"
    )
    headers = {"accept": "*/*"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def sanitize_group_name(name: str) -> str:
    """Strip punctuation and spaces from name for group column."""
    return re.sub(r"[^\w]", "", name)

def get_freq_duration(node_id) -> str:
    url = f"https://api.pennsieve.io/packages/download-manifest?api_key={API_KEY}"

    payload = { "nodeIds": [node_id] }
    headers = {
        "accept": "*/*",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response_json = response.json()
    data = response_json["data"]
    for payload in data:
        download_url = payload["url"]

    response = requests.get(download_url)
    response.raise_for_status()
    ieeg_json =  response.json()

    sampling_frequency = ieeg_json.get("SamplingFrequency","n/a")
    duration = ieeg_json.get("RecordingDuration","n/a")

    return {"sampling_frequency": sampling_frequency, "duration": duration}

def get_electrode_data(node_id: str, api_key: str):
    manifest_url = "https://api.pennsieve.io/packages/download-manifest"

    payload = {"nodeIds": [node_id]}
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    resp = requests.post(f"{manifest_url}?api_key={api_key}", json=payload, headers=headers)
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

    # Step 3: Parse CSV directly into memory
    csv_text = file_resp.text
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    return rows

def make_output_name(dataset_name: str) -> str:
    """
    Convert dataset name like 'EPS00049' → 'PENNEPI00049'.
    Handles any EPS prefix with variable zeros.
    """
    match = re.search(r"(\d+)", dataset_name)
    num = match.group(1) if match else "00000"
    return f"PennEPI{int(num):05d}"

def clean_basename(pkg_name: str) -> str:
    name = pkg_name.lower().removesuffix(".mef")
    name = re.sub(r"(eeg|-ref)", "", name)
    name = name.translate(str.maketrans("", "", string.punctuation))
    return name.strip().upper() 