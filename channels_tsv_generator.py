import csv
import os
import re
import json
import string
import requests
from urllib.parse import quote


API_KEY = ""
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
        f"pageSize=100&includeSourceFiles=false&api_key={API_KEY}"
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


def get_sampling_frequency_from_json(filename: str) -> str:
    try:
        with open(f"{IEEG_JSON_PATH}/ieeg.json","r") as f:
            data = json.load(f)
            return data["SamplingFrequency"]
    except FileNotFoundError as file_not_found_err:
        print(f"Error opening file: {file_not_found_err}")
    except json.JSONDecodeError as json_error:
        print(f"Json Decode error: {json_error}")


def make_output_name(dataset_name: str) -> str:
    """
    Convert dataset name like 'EPS00049' → 'PENNEPI00049'.
    Handles any EPS prefix with variable zeros.
    """
    match = re.search(r"(\d+)", dataset_name)
    num = match.group(1) if match else "00000"
    return f"PennEPI-{int(num):05d}"

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

        rows = []
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            pkg_name = pkg_content.get("name", "")
            if not pkg_name.lower().endswith(".mef"):
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
            sampling_freq = get_sampling_frequency_from_json(pkg_name)

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
