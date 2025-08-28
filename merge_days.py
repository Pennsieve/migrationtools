import os
import sys
import shutil
import re
import csv
from pathlib import Path

def numeric_key(folder: Path):
    match = re.search(r"EPS(\d+)", folder.name)
    return int(match.group(1)) if match else float('inf')

# Get input directory from CLI
if len(sys.argv) != 2:
    print("❌ Usage: python merge_days.py <EPS_PARENT_FOLDER>")
    sys.exit(1)

base_dir = Path(sys.argv[1])
if not base_dir.exists() or not base_dir.is_dir():
    print(f"❌ Provided input is not a valid directory: {base_dir}")
    sys.exit(1)

# Get suffixes from CSV
mapping_file = Path.home() / "migrationtools" / "migration_paths.csv"
if not mapping_file.exists():
    print(f"❌ Could not find mapping file at {mapping_file}")
    sys.exit(1)

ordered_suffixes = []
with mapping_file.open("r", newline="") as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if row and len(row[0].strip()) > 0:
            match = re.search(r"_D\d{2}", row[0])
            if match:
                ordered_suffixes.append(match.group()[1:])
            else:
                print(f"⚠️ Skipping malformed row: {row[0]}")

if not ordered_suffixes:
    print("❌ No valid entries found in migration_paths.csv")
    sys.exit(1)

# Find and sort EPS folders
eps_folders = sorted(
    [d for d in base_dir.iterdir() if d.is_dir() and re.match(r"EPS\d+", d.name)],
    key=numeric_key
)

if len(eps_folders) < 2:
    print("❌ Not enough EPS folders found.")
    sys.exit(1)

if len(ordered_suffixes) < len(eps_folders):
    print(f"❌ Not enough suffixes in mapping file: found {len(ordered_suffixes)}, need {len(eps_folders)}")
    sys.exit(1)

main_folder = eps_folders[0]
main_id = main_folder.name
print(f"✅ Main folder: {main_id}")

# Output path
ieeg_base = main_folder / "primary" / f"sub-{main_id}" / "ses-postimplant" / "ieeg"
ieeg_base.mkdir(parents=True, exist_ok=True)

# Loop and process
for eps, suffix in zip(eps_folders, ordered_suffixes):
    eps_id = eps.name
    print(f"\n➡️  Processing {eps_id} as {suffix}")

    ieeg_folder = eps / "primary" / f"sub-{eps_id}" / "ses-postimplant" / "ieeg"
    target_ieeg_dir = ieeg_base / suffix
    target_ieeg_dir.mkdir(parents=True, exist_ok=True)

    if ieeg_folder.exists():
        for item in ieeg_folder.iterdir():
            if item.is_file():
                target = target_ieeg_dir / item.name
                shutil.move(str(item), str(target))
            else:
                print(f"    ⚠️ Skipping folder inside ieeg: {item.name}")
    else:
        print(f"    ⚠️ No ieeg folder found for {eps_id}, skipping MEF move.")

    primary_folder = eps / "primary"
    if not primary_folder.exists():
        continue

    for item in primary_folder.iterdir():
        if item.name.startswith("sub-"):
            continue
        if not item.is_file():
            print(f"    ⚠️ Skipping non-file in primary/: {item.name}")
            continue

        dest_folder = main_folder / "primary"
        dest_folder.mkdir(parents=True, exist_ok=True)

        if eps == main_folder:
            dest = dest_folder / item.name
            if item.resolve() == dest.resolve():
                print(f"    ✅ Skipping self-move for {item.name}")
                continue
            print(f"    ✅ Moving original file: {item.name}")
        else:
            new_name = f"{item.stem}_{suffix}{item.suffix}"
            dest = dest_folder / new_name
            print(f"    🔁 Moving child file: {item.name} → {new_name}")

        shutil.move(str(item), str(dest))

print("\n✅ All done.")
