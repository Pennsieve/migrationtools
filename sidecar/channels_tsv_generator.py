from helpers import *
import os, csv
from pathlib import Path

def get_ref_gnd_map(csv_path):
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

def main():
    keys_to_check = ["D01", "D02", "D03", "D04", "D05", "D06", "D07"]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching all datasets...")
    datasets = load_data("datasets")
    if datasets is None:
        print("Fetching all packages from network...")
        datasets = get_all_datasets()
        save_data(datasets, "datasets")
        
    print(f"Total datasets fetched: {len(datasets)}")

    master_map = get_ref_gnd_map(MASTER_CSV_PATH)
    payload = {}
    sub_dataset_tracker = {}
    parent_id_reference = {}
        
    # Build up parent id reference for later use
    build_parent_id_ref(datasets, payload, sub_dataset_tracker, parent_id_reference)    

    # Loop over all datasets and packages
    for ds in datasets:
        dataset_name = ds["content"]["name"]
        ds_id = ds["content"]["id"]
        
        if not dataset_name.lower().startswith("eps") and not dataset_name.lower().startswith("pennepi"):
            continue

        packages = load_data(f"package_{dataset_name}")
        if packages is None:
            print("Fetching all packages from network...")
            packages = get_dataset_packages(ds_id)
            save_data(packages, f"package_{dataset_name}")

        sampling_freq = "n/a"

        # Get sampling frequency and duration, per sub dataset
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            if pkg_content.get("state") == "DELETED" or pkg_content.get("state") == "DELETING":
                continue
            pkg_name = pkg_content.get("name", "")
            ieeg_json = pkg_name.lower().strip().endswith("implant_ieeg.json")
            is_electrodes_csv = pkg_name.lower().strip() == "electrodes2roi_mni.csv"
            is_electrodes_txt = pkg_name.lower().strip() == "electodes.txt"
            
            if not ieeg_json and not is_electrodes_csv and not is_electrodes_txt:
                continue    
            
            if ieeg_json:
                node_id = pkg.get("content").get("nodeId")
                
                ieeg_json_data = load_data(f"ieeg_json_data_{node_id}")
                if ieeg_json_data is None:
                    print("Fetching all packages from network...")
                    ieeg_json_data = get_freq_duration(node_id)
                    save_data(ieeg_json_data,f"ieeg_json_data_{node_id}")

                sampling_freq = ieeg_json_data["sampling_frequency"]
                duration = ieeg_json_data["duration"]

                keys_to_check = ["D01", "D02", "D03", "D04", "D05"]

                if parent_id_reference[dataset_name].get(pkg_content.get("parentId")) in keys_to_check:
                    parent_id = pkg_content.get("parentId")
                    
                    payload[dataset_name][parent_id_reference[dataset_name][parent_id]]["sampling_frequency"] = sampling_freq
                    payload[dataset_name][parent_id_reference[dataset_name][parent_id]]["duration"] = duration
                else:
                    payload[dataset_name]["sampling_frequency"] = sampling_freq
                    payload[dataset_name]["duration"] = duration


            if is_electrodes_csv:
                # Save electrode csv data out since we'll need it later
                node_id = pkg_content.get("nodeId")
                electrode_data = load_data(f"electrode_data_{dataset_name}")

                if electrode_data is None:
                    print("Fetching electrode csv data from network...")
                    electrode_data = get_electrode_data(node_id)
                    save_data(electrode_data, f"electrode_data_{dataset_name}")

            if is_electrodes_txt:
                # Save electrode txt data out since we'll need it later
                node_id = pkg_content.get("nodeId")
                electrode_data = load_data(f"electrode_txt_data_{dataset_name}")

                if electrode_data is None:
                    print("Fetching electrode txt data from network...")
                    electrode_data = get_electrode_data(node_id)
                    parsed_data = parse_electrode_txt(electrode_data)
                    save_data(parsed_data, f"electrode_txt_data_{dataset_name}") 
                

        rows = []
        rows_by_parent = {}
        
        # build up row object for tsv writing
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            pkg_name = pkg_content.get("name", "")
            mef = pkg_name.lower().endswith(".mef")
            

            if not mef or pkg_content.get("state") == "DELETED" or pkg_content.get("state") == "DELETING":
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
                master_map_key = dataset_name
                if dataset_name == "PennEPI00049":
                    master_map_key = "EPS0000049"
                reference, ground = master_map.get(master_map_key, ("unknown", "unknown"))

            group = sanitize_group_name(base_name)[:2]
            if group.lower() in ["ek","ec"]:
                group = "n/a"

            parent_id = parent_id = pkg_content.get("parentId")

            row ={
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
            }

            rows_by_parent.setdefault(parent_id, []).append(row)
        
        # Add rows to payload:  rows_by_parent
        for parent_id, rows in rows_by_parent.items():
            rows.sort(key=lambda r: r["name"].lower())
            

            if any(k in payload[dataset_name] for k in keys_to_check):
                parent_key = parent_id_reference[dataset_name].get(parent_id)
                if parent_key:
                    payload[dataset_name][parent_key]["row_data"] = rows
            else:
                payload[dataset_name]["row_data"] = rows
 

        # loop through rows_by_parent and save to file
        for parent_id, rows in rows_by_parent.items():
            rows.sort(key=lambda r: r["name"].lower())

            if any(k in payload[dataset_name] for k in keys_to_check):
                #  multi-day / sub-dataset case
                parent_key = parent_id_reference[dataset_name].get(parent_id)
                if not parent_key:
                    continue

                # TODOD: Check on ieeg ground and reference
                payload[dataset_name][parent_key]["row_data"] = rows

                top_folder = make_output_name(dataset_name) # e.g. PennEPI
                full_output_path = Path(OUTPUT_DIR) / top_folder / "bids"/ parent_key # PennEPI/D01
                full_output_path.mkdir(parents=True, exist_ok=True)

                output_path = full_output_path / f"sub-{top_folder}-postimplant_channels.tsv"
                # print(f"Writing {len(rows)} rows → {output_path}")

                fieldnames = [
                    "name", "type", "units", "low_cutoff", "high_cutoff",
                    "reference", "ground", "group", "sampling_frequency", "notch"
                ]
                with open(output_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
                    writer.writeheader()
                    writer.writerows(rows)

            else:
                # single-dataset case (no D0X keys)
                payload[dataset_name]["row_data"] = rows

                top_folder = make_output_name(dataset_name) # e.g. EPS005
                full_output_path = Path(OUTPUT_DIR) / top_folder/"bids" # EPS005/
                full_output_path.mkdir(parents=True, exist_ok=True)

                output_path = full_output_path / f"sub-{top_folder}-postimplant_channels.tsv"
                # print(f"Writing {len(rows)} rows → {output_path}")

                fieldnames = [
                    "name", "type", "units", "low_cutoff", "high_cutoff",
                    "reference", "ground", "group", "sampling_frequency", "notch"
                ]
                with open(output_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
                    writer.writeheader()
                    writer.writerows(rows)
                    

    save_data(payload, f"payload")
    print("\n✅ Done\n")

def build_parent_id_ref(datasets, payload, sub_dataset_tracker, parent_id_reference):
    for ds in datasets:
        dataset_name = ds["content"]["name"]
        ds_id = ds["content"]["id"]

        payload[dataset_name] = {}
        parent_id_reference[dataset_name] = {}
        packages = load_data(f"package_{dataset_name}")
        if packages is None:
            print("Fetching all packages from network...")
            packages = get_dataset_packages(ds_id)
            save_data(packages, f"package_{dataset_name}")

        sub_dataset_tracker[dataset_name] = {}
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            pkg_name = pkg_content.get("name", "")
            if pkg_name.lower().strip().startswith("d0"):
                # set the parent ID as a key
                parent_id_reference[dataset_name].update({pkg_content.get("id",""): pkg_name})
                payload[dataset_name].update({pkg_name: {
                    "sampling_frequency": None,
                    "duration": None,
                }})
            else:
                payload[dataset_name].update({
                    "sampling_frequency": None,
                    "duration": None,
                })
    


if __name__ == "__main__":
    main()
