import csv
import os
import re
import sys
import string
import requests
from urllib.parse import quote


API_KEY = os.getenv("API_KEY")
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


def load_master_metadata(csv_path):
    """Load EPS → (reference, ground) mapping from master CSV."""
    mapping = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eps = row.get("EPS Number")
            if eps:
                mapping[eps.strip()] = (
                    row.get("iEEGReference", "").strip() or "unknown",
                    row.get("iEEGGround", "").strip() or "unknown",
                )
    return mapping


def sanitize_group_name(name: str) -> str:
    """Strip punctuation and spaces from name for group column."""
    return re.sub(r"[^\w]", "", name)


def get_sampling_frequency_from_json(node_id) -> str:
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
    return ieeg_json.get("SamplingFrequency","n/a")

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


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching all datasets...")
    datasets = get_all_datasets()
    print(f"Total datasets fetched: {len(datasets)}")

    master_map = load_master_metadata(MASTER_CSV_PATH)

    for ds in datasets:
        name = ds["content"]["name"]
        ds_id = ds["content"]["id"]

        if not name.startswith("EPS"):
            continue

        print(f"\nProcessing dataset: {name}")

        pkg_data = get_dataset_packages(ds_id)
        packages = pkg_data.get("packages", [])
        
        sampling_freq = "n/a"

        # Get sampling frequency
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            if pkg_content.get("state") == "DELETED":
                continue
            pkg_name = pkg_content.get("name", "")
            ieeg_json = pkg_name.lower().strip().endswith("implant_ieeg.json")
            
            if not ieeg_json:
                continue

            node_id = pkg.get("content").get("nodeId")
            sampling_freq = get_sampling_frequency_from_json(node_id)


        rows = []
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            pkg_name = pkg_content.get("name", "")
            mef = pkg_name.lower().endswith(".mef")
            
            if not mef:
                continue

            base_name = clean_basename(pkg_name)
            

            is_ekg = "ekg" in base_name.lower()

            # Fill columns
            type_ = "ECG" if is_ekg else "SEEG"
            units = "uV"
            low_cutoff = "n/a"
            high_cutoff = "0.01" if not is_ekg else "n/a"
            notch = "n/a"

            if is_ekg:
                reference = "unknown"
                ground = "unknown"
            else:
                reference, ground = master_map.get(name, ("unknown", "unknown"))

            group = sanitize_group_name(base_name)[:2]

            rows.append({
                "name": base_name,
                "type": type_,
                "units": units,
                "low_cutoff": low_cutoff,
                "high_cutoff": high_cutoff,
                "reference": reference,
                "ground": ground,
                "group": group,
                "sampling_frequency": sampling_freq,
                "notch": notch,
            })

        if not rows:
            print(f"⚠️ No .mef files found in {name}, skipping.")
            continue

        rows.sort(key=lambda r: r["name"].lower())

        output_name = make_output_name(name)
        output_path = os.path.join(OUTPUT_DIR, f"{output_name}.csv")

        print(f"Writing {len(rows)} rows → {output_path}")

        fieldnames = [
            "name", "type", "units", "low_cutoff", "high_cutoff",
            "reference", "ground", "group", "sampling_frequency", "notch"
        ]

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("\n✅ Done\n")


if __name__ == "__main__":
    main()
