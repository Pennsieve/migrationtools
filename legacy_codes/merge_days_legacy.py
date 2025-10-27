import os
import sys
import shutil
import re
import csv
from pathlib import Path
from collections import defaultdict
from typing import Optional

print("----- Starting merge_days.py -----")



# --- helper functions ---
# Extract and convert to number the part after third hyphen for sorting
def numeric_key(folder: Path):
    # Split by hyphens and get the part after the third hyphen
    parts = folder.name.split('-', 3)  # split max 3 times
    
    # Get the first number (integer or float) from the last part
    # This will match patterns like "3", "3.5", "01", etc. at the start of the string
    match = re.match(r'(\d+\.?\d*)', parts[3])
    if match:
        return float(match.group(1))

    return float('inf')  # No valid number found, return +inf so such names sort to the end 

# extract and normalize suffix from PRV folder names PRV-XXX-XXXX-<suffix>
def extract_and_normalize_suffix(cell: str) -> Optional[str]:

    cell = cell.strip()
    # expect at least three hyphens; capture the rest as suffix.
    m = re.match(r'^[^-]*-[^-]*-[^-]*-(.*)$', cell)
    if not m:
        print(f"WARNING: Could not extract suffix from: {cell}")
        return None
    raw = m.group(1).strip() # gets the content of the first capturing group, trim any whitespace from the begining or the end 

    # sub parentheses with underscore: "01(2)" -> "01-2"
    norm = re.sub(r'\(([^)]+)\)', r'-\1', raw)    
    # sub internal whitespace to underscores: "01 ses" -> "01_ses"
    norm = re.sub(r'\s+', '_', norm)
    # replace anything not alnum, underscore, dot, hyphen with underscore
    norm = re.sub(r'[^A-Za-z0-9_.-]', '_', norm)

    # add 'D' prefix to the normalized string to make their folder name  
    norm = f"D{norm}"
    return norm



# --- checkers --- 
# Get input directory from CLI - should be /data/
if len(sys.argv) != 2:
    print("❌ Usage: python merge_days.py <EPS_PARENT_FOLDER>")
    sys.exit(1)

# Validate base directory - base_dir should be /data/
base_dir = Path(sys.argv[1])
if not base_dir.exists() or not base_dir.is_dir():
    print(f"❌ Provided input is not a valid directory: {base_dir}")
    sys.exit(1)

# Get suffixes from CSV
mapping_file = Path.home() / "migrationtools" / "migration_paths.csv"
if not mapping_file.exists():
    print(f"❌ Could not find mapping file at {mapping_file}")
    sys.exit(1)

# ordered_suffixes would hold suffixes (D01, D02, ...)
ordered_suffixes = []
with mapping_file.open("r", newline="") as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if row and len(row[0].strip()) > 0: # skip empty rows 
            suffix = extract_and_normalize_suffix(row[0])
            if suffix:
                ordered_suffixes.append(suffix)
            else:
                print(f"⚠️ Skipping malformed row: {row[0]}")

if not ordered_suffixes:
    print("❌ No valid entries found in migration_paths.csv")
    sys.exit(1)

# Find and sort PRV folders
prv_folders = sorted(
    [d for d in base_dir.iterdir() if d.is_dir() and re.match(r"PRV-[^-]+-[^-]+-", d.name)],
    key=numeric_key
)

# each patient need at least 2 days to merge 
if len(prv_folders) < 2:
    print("❌ Not enough PRV folders found.")
    sys.exit(1)

# for each of the RPV session folder, there should be a suffix 
if len(ordered_suffixes) < len(prv_folders):
    print(f"❌ Not enough suffixes in mapping file: found {len(ordered_suffixes)}, need {len(prv_folders)}")
    sys.exit(1)

# the smallest prv number will be the main folder
main_folder = prv_folders[0]
main_id = main_folder.name
print(f"✅ Main folder: {main_id}")

# Output path
ieeg_base = main_folder / "primary" / f"sub-{main_id}" / "ses-postimplant" / "ieeg"
ieeg_base.mkdir(parents=True, exist_ok=True)



# --- main loop ---
# Loop and process
for prv, suffix in zip(prv_folders, ordered_suffixes):
    prv_id = prv.name # prv_id as folder name for each patient session folder under /data/
    print(f"\n➡️  Processing {prv_id} as {suffix}")

    ieeg_folder = prv / "primary" / f"sub-{prv_id}" / "ses-postimplant" / "ieeg"
    target_ieeg_dir = ieeg_base / suffix # mkdir for the exact patient session folder to cp (.../ieeg/Dxx)
    target_ieeg_dir.mkdir(parents=True, exist_ok=True)

    if ieeg_folder.exists():
        for item in ieeg_folder.iterdir(): # iterate entries under ../ieeg (sub-dir and files like .mef, .tsv, and .json?)
            if item.is_file(): # only process files, skip directories
                target = target_ieeg_dir / item.name 
                shutil.move(str(item), str(target)) # move files from .../ieeg/ to .../ieeg/Dxx
            else:
                print(f"    ⚠️ Skipping folder inside ieeg: {item.name}")
    else:
        print(f"    ⚠️ No ieeg folder found for {prv_id}, skipping MEF move.")

    primary_folder = prv / "primary"
    if not primary_folder.exists():
        continue

    for item in primary_folder.iterdir():
        if item.name.startswith("sub-"): # to select only files rather than "sub-" folders 
            continue
        if not item.is_file():
            print(f"    ⚠️ Skipping non-file in primary/: {item.name}")
            continue

        dest_folder = main_folder / "primary" # the smallest prv-numbered folder 
        dest_folder.mkdir(parents=True, exist_ok=True)

        # move files from non-main folders to the main folder's primary directory, rename them to include their suffix 
        if prv == main_folder: 
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

# After all moves are done, rename directories to remove suffixes
# First get the base name (only the first three parts before the third hyphen)
parts = main_id.split("-", 3)  # split max 3 times, similar to numeric_key function
base_name = "-".join(parts[:3])  # Take only the first three parts

# Rename the sub directory first (deeper in the tree)
main_sub_dir = main_folder / "primary" / f"sub-{main_id}"
if main_sub_dir.exists():
    new_sub_dir = main_folder / "primary" / f"sub-{base_name}"
    print(f"\n✅ Renaming main sub directory:\n    {main_sub_dir.name} → {new_sub_dir.name}")
    shutil.move(str(main_sub_dir), str(new_sub_dir))

# Then rename the main folder itself
new_main_folder = main_folder.parent / base_name
print(f"✅ Renaming main folder:\n    {main_folder.name} → {new_main_folder.name}")
shutil.move(str(main_folder), str(new_main_folder))

print("----- Finishing merge_days.py -----")