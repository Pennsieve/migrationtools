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
            
            if not ieeg_json and not is_electrodes_csv:
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

                # Write duration to file for later use
                try:
                    penn_epi_name = make_output_name(dataset_name)
                    recording_duration_output = os.path.join(OUTPUT_DIR, "recording_durations")
                    path = Path(recording_duration_output) / f"{penn_epi_name}_recording_duration"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(str(duration))
                except Exception as e:
                    print(f"Could not write to file: {e}")


            if is_electrodes_csv:
                node_id = pkg_content.get("nodeId")
                electrode_data = load_data(f"electrode_data_{node_id}")

                if electrode_data is None:
                    print("Fetching electrode data from network...")
                    electrode_data = get_electrode_data(node_id)
                    save_data(electrode_data, f"electrode_data_{node_id}")

                # Determine which D0X this belongs to (if any)
                parent_id = pkg_content.get("parentId")
                parent_key = parent_id_reference[dataset_name].get(parent_id)

                # Build electrode rows
                electrode_rows = []
                for e in electrode_data:
                    name = e.get("labels", "").strip()
                    if not name:
                        continue
                    electrode_rows.append({
                        "name": name,
                        "x": e.get("mm_x", ""),
                        "y": e.get("mm_y", ""),
                        "z": e.get("mm_z", ""),
                        "size": 2,
                        "hemisphere": name[0].upper(),
                        "group": name[:2].upper(),
                        "type": "SEEG",
                        "roi": e.get("roi", ""),
                    })

                # Decide output folder
                top_folder = make_output_name(dataset_name)
                if parent_key and parent_key in payload[dataset_name]:
                    full_output_path = Path(OUTPUT_DIR) / top_folder / parent_key
                else:
                    full_output_path = Path(OUTPUT_DIR) / top_folder

                full_output_path.mkdir(parents=True, exist_ok=True)

                # Write electrodes.tsv
                electrode_path = full_output_path / "electrodes.tsv"
                print(f"Writing {len(electrode_rows)} electrodes → {electrode_path}")

                fieldnames = [
                    "name", "x", "y", "z", "size",
                    "hemisphere", "group", "type", "roi"
                ]
                with open(electrode_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
                    writer.writeheader()
                    writer.writerows(electrode_rows)

                

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
                reference, ground = master_map.get(dataset_name, ("unknown", "unknown"))

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

                payload[dataset_name][parent_key]["row_data"] = rows

                top_folder = make_output_name(dataset_name) # e.g. EPS004
                full_output_path = Path(OUTPUT_DIR) / top_folder / parent_key # EPS004/D01
                full_output_path.mkdir(parents=True, exist_ok=True)

                output_path = full_output_path / "channels.tsv"
                print(f"Writing {len(rows)} rows → {output_path}")

                fieldnames = [
                    "counter", "name", "type", "units", "low_cutoff", "high_cutoff",
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
                full_output_path = Path(OUTPUT_DIR) / top_folder # EPS005/
                full_output_path.mkdir(parents=True, exist_ok=True)

                output_path = full_output_path / "channels.tsv"
                print(f"Writing {len(rows)} rows → {output_path}")

                fieldnames = [
                    "counter", "name", "type", "units", "low_cutoff", "high_cutoff",
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
