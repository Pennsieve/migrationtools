import os
import sys
import shutil
import re
import csv
from pathlib import Path
from collections import defaultdict

print("----- Starting merge_days.py -----")

# Get input directory from CLI:
if len(sys.argv) != 2:
    print("❌ Usage: python merge_days.py <EPS_PARENT_FOLDER>")
    sys.exit(1)

base_dir = Path(sys.argv[1])
if not base_dir.exists() or not base_dir.is_dir():
    print(f"❌ Provided input is not a valid directory: {base_dir}")
    sys.exit(1)

# Get mapping from CSV
mapping_file = Path.home() / "migrationtools" / "migration_paths.csv"
if not mapping_file.exists():
    print(f"❌ Could not find mapping file at {mapping_file}")
    sys.exit(1)

# Group folders by shared prefix
grouped_folders = defaultdict(list)
with mapping_file.open("r", newline="") as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if row and len(row[0].strip()) > 0:
            # Extract the shared prefix 
            match = re.match(r"(PRV-\d{3}-[A-Za-z0-9]+)-", row[0])
            if match:
                prefix = match.group(1)
                grouped_folders[prefix].append(row[0])
            else:
                print(f"⚠️ Skipping malformed row: {row[0]}")

if not grouped_folders:
    print("❌ No valid entries found in migration_paths.csv")
    sys.exit(1)

# Process each group
for prefix, entries in grouped_folders.items():
    print(f"\n➡️  Processing group: {prefix}")
    eps_folders = [base_dir / entry for entry in entries if (base_dir / entry).exists()]

    if len(eps_folders) < 2:
        print(f"    ⚠️ Not enough folders to merge for group {prefix}. Skipping.")
        continue

    # Designate the first folder as the main folder
    main_folder = eps_folders[0]
    print(f"    ✅ Main folder: {main_folder.name}")

    # Output path
    ieeg_base = main_folder / "primary" / f"sub-{main_folder.name}" / "ses-postimplant" / "ieeg"
    ieeg_base.mkdir(parents=True, exist_ok=True)

    # Loop and process
    for eps in eps_folders:
        if eps == main_folder:
            continue

        eps_id = eps.name
        print(f"    🔁 Merging {eps_id} into {main_folder.name}")

        # Move iEEG files
        ieeg_folder = eps / "primary" / f"sub-{eps_id}" / "ses-postimplant" / "ieeg"
        target_ieeg_dir = ieeg_base / eps_id
        target_ieeg_dir.mkdir(parents=True, exist_ok=True)

        if ieeg_folder.exists():
            for item in ieeg_folder.iterdir():
                if item.is_file():
                    target = target_ieeg_dir / item.name
                    shutil.move(str(item), str(target))
                else:
                    print(f"        ⚠️ Skipping folder inside ieeg: {item.name}")
        else:
            print(f"        ⚠️ No ieeg folder found for {eps_id}, skipping MEF move.")

        # Move other files in `primary`
        primary_folder = eps / "primary"
        if not primary_folder.exists():
            continue

        for item in primary_folder.iterdir():
            if item.name.startswith("sub-"):
                continue
            if not item.is_file():
                print(f"        ⚠️ Skipping non-file in primary/: {item.name}")
                continue

            dest_folder = main_folder / "primary"
            dest_folder.mkdir(parents=True, exist_ok=True)

            new_name = f"{item.stem}_{eps_id}{item.suffix}"
            dest = dest_folder / new_name
            print(f"        🔁 Moving file: {item.name} → {new_name}")

            shutil.move(str(item), str(dest))

print("----- Finishing merge_days.py -----")