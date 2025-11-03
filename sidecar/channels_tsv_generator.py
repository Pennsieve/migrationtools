from helpers import *


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
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching all datasets...")
    datasets = get_all_datasets()
    print(f"Total datasets fetched: {len(datasets)}")

    master_map = get_ref_gnd_map(MASTER_CSV_PATH)
    
    for ds in datasets:
        name = ds["content"]["name"]
        ds_id = ds["content"]["id"]

        # if not name.lower().strip().startswith("pennepi"):
        #     # print(f"temp skip for {name}")
        #     continue

        if not name.lower().startswith("eps") and not name.lower().startswith("pennepi"):
            continue

        print(f"\nProcessing dataset: {name}")

        pkg_data = get_dataset_packages(ds_id)
        packages = pkg_data.get("packages", [])
        
        sampling_freq = "n/a"

        # Get sampling frequency
        for pkg in packages:
            pkg_content = pkg.get("content", {})
            if pkg_content.get("state") == "DELETED" or pkg_content.get("state") == "DELETING":
                continue
            pkg_name = pkg_content.get("name", "")

            ieeg_json = pkg_name.lower().strip().endswith("implant_ieeg.json")
            is_electrodes_csv = pkg_name.lower().strip() == "electrodes2roi_mni.csv"
            # print(pkg_name.lower().strip())
            
            if not ieeg_json and not is_electrodes_csv:
                continue

            if ieeg_json:
                node_id = pkg.get("content").get("nodeId")
                ieeg_json_data = get_freq_duration(node_id)

                sampling_freq = ieeg_json_data["sampling_frequency"]
                duration = ieeg_json_data["duration"]

                # Write duration to file for later use
                try:
                    penn_epi_name = make_output_name(name)
                    recording_duration_output = os.path.join(OUTPUT_DIR, "recording_durations")
                    path = Path(recording_duration_output) / f"{penn_epi_name}_recording_duration"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(str(duration))
                except Exception as e:
                    print(f"Could not write to file: {e}")

            if is_electrodes_csv:
                node_id = pkg.get("content").get("nodeId")
                electrode_data = get_electrode_data(node_id)
                print(electrode_data)
                breakpoint()

        rows = []
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
                reference, ground = master_map.get(name, ("unknown", "unknown"))

            group = sanitize_group_name(base_name)[:2]
            if group.lower() in ["ek","ec"]:
                group = "n/a"

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
        full_output_path = os.path.join(OUTPUT_DIR, output_name, 'bids')
        os.makedirs(full_output_path, exist_ok=True)
        output_path = os.path.join(full_output_path, f"channels.tsv")

        print(f"Writing {len(rows)} rows → {output_path}")

        fieldnames = [
            "name", "type", "units", "low_cutoff", "high_cutoff",
            "reference", "ground", "group", "sampling_frequency", "notch"
        ]

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    print("\n✅ Done\n")


if __name__ == "__main__":
    main()
