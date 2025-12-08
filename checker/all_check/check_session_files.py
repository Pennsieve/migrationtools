'''
Check each session folder in Pennsieve datasets to ensure they contain
at least one of each required file type: EDF, XML, TSV, JSON.
'''

import csv
import os
import re
import sys
from collections import defaultdict

# Add parent directories to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(CHECKER_DIR)
sys.path.insert(0, ROOT_DIR)

from helpers import get_all_datasets, get_dataset_packages, API_KEY

# Output paths relative to checker directory
OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "all_check")
OUTPUT_REPORT = os.path.join(OUTPUT_DIR, "session_file_check_report.csv")

DRY_RUN = False  # True = just list datasets, don't check packages
TARGET_DATASETS = ["*"]  # ["*"] for all PREVeNT, or list specific dataset names

os.makedirs(OUTPUT_DIR, exist_ok=True)

REQUIRED_EXTENSIONS = {
    'edf': '.edf',
    'xml': '.xml',
    'tsv': '.tsv',
    'json': '.json'
}


def should_process_dataset(dataset_name: str) -> bool:
    """Check if dataset should be processed based on TARGET_DATASETS."""
    if not dataset_name:
        return False
    if not dataset_name.startswith("PREVeNT"):
        return False
    if TARGET_DATASETS == ["*"]:
        return True
    return dataset_name in TARGET_DATASETS


def extract_patient_id_from_dataset(dataset_name: str) -> str:
    """
    Extract patient ID from dataset name.
    e.g., 'PREVeNT Trial 166V' -> '166V'
    """
    match = re.match(r"PREVeNT Trial (.+)", dataset_name)
    if match:
        return match.group(1).strip()
    return None


def build_folder_tree(packages: list) -> dict:
    """
    Build a tree structure of folders and their contents.
    Returns: {folder_path: {files: [list of files], subfolders: [list]}}
    """
    # Build ID to package lookup
    id_to_pkg = {}
    for pkg in packages:
        content = pkg.get("content", {})
        pkg_id = content.get("id")
        if pkg_id:
            id_to_pkg[pkg_id] = pkg

    # Build path for each package
    def get_path(pkg):
        content = pkg.get("content", {})
        name = content.get("name", "")
        parent_id = content.get("parentId")

        path_parts = [name]
        visited = set()
        current_parent = parent_id

        while current_parent and current_parent not in visited:
            visited.add(current_parent)
            parent_pkg = id_to_pkg.get(current_parent)
            if parent_pkg:
                parent_content = parent_pkg.get("content", {})
                parent_name = parent_content.get("name", "")
                if parent_name:
                    path_parts.insert(0, parent_name)
                current_parent = parent_content.get("parentId")
            else:
                break

        return "/".join(path_parts)

    # Build folder contents
    folder_contents = defaultdict(lambda: {"files": [], "subfolders": set()})

    for pkg in packages:
        content = pkg.get("content", {})
        pkg_name = content.get("name", "")
        pkg_type = content.get("packageType", "")

        full_path = get_path(pkg)

        # Determine parent folder path
        if "/" in full_path:
            parent_path = "/".join(full_path.split("/")[:-1])
        else:
            parent_path = ""

        # If it's a collection (folder), register it
        if pkg_type == "Collection":
            folder_contents[full_path]["files"]  # Initialize
            if parent_path:
                folder_contents[parent_path]["subfolders"].add(pkg_name)
        else:
            # It's a file, add to parent folder
            folder_contents[parent_path]["files"].append(pkg_name)

    return folder_contents


def find_session_folders(folder_contents: dict) -> list:
    """
    Find all session folders (folders matching 'ses-visit*' pattern).
    Returns list of (folder_path, folder_name) tuples.
    """
    session_folders = []
    session_pattern = re.compile(r"ses-visit[\d.]+m")

    for folder_path in folder_contents.keys():
        folder_name = folder_path.split("/")[-1] if "/" in folder_path else folder_path
        if session_pattern.match(folder_name):
            session_folders.append((folder_path, folder_name))

    return session_folders


def check_required_files(files: list) -> dict:
    """
    Check if required file types are present.
    Returns dict with extension -> [list of matching files]
    """
    found = {ext: [] for ext in REQUIRED_EXTENSIONS.keys()}

    for filename in files:
        filename_lower = filename.lower()
        for ext_name, ext in REQUIRED_EXTENSIONS.items():
            if filename_lower.endswith(ext):
                found[ext_name].append(filename)

    return found


def get_all_files_in_session(folder_path: str, folder_contents: dict) -> list:
    """
    Get all files in a session folder and its subfolders (like 'eeg' subfolder).
    """
    all_files = []

    # Get files directly in the session folder
    if folder_path in folder_contents:
        all_files.extend(folder_contents[folder_path]["files"])

    # Check common subfolders like 'eeg'
    for subfolder in folder_contents.get(folder_path, {}).get("subfolders", []):
        subfolder_path = f"{folder_path}/{subfolder}"
        if subfolder_path in folder_contents:
            all_files.extend(folder_contents[subfolder_path]["files"])

    return all_files


def check_session_files():
    """Main function to check session folders for required files."""

    print("Fetching datasets from Pennsieve...")
    datasets = get_all_datasets()
    print(f"Found {len(datasets)} total datasets")

    all_issues = []
    all_sessions_checked = []

    for ds in datasets:
        dataset_name = ds.get("content", {}).get("name", "")
        dataset_id = ds.get("content", {}).get("id")

        if not should_process_dataset(dataset_name):
            continue

        patient_id = extract_patient_id_from_dataset(dataset_name)

        print(f"\n{'='*60}")
        print(f"Dataset: {dataset_name}")

        if DRY_RUN:
            print("  [DRY RUN] Would check packages")
            continue

        # Get all packages
        try:
            packages = get_dataset_packages(dataset_id)
            print(f"  Found {len(packages)} packages")
        except Exception as e:
            print(f"  Error fetching packages: {e}")
            all_issues.append({
                "dataset": dataset_name,
                "patient_id": patient_id,
                "session": "N/A",
                "error": f"Failed to fetch packages: {e}",
                "missing_edf": "",
                "missing_xml": "",
                "missing_tsv": "",
                "missing_json": ""
            })
            continue

        # Build folder tree
        folder_contents = build_folder_tree(packages)

        # Find session folders
        session_folders = find_session_folders(folder_contents)
        print(f"  Found {len(session_folders)} session folders")

        for folder_path, session_name in session_folders:
            # Get all files in session (including subfolders like 'eeg')
            all_files = get_all_files_in_session(folder_path, folder_contents)

            # Check for required files
            found_files = check_required_files(all_files)

            # Determine what's missing
            missing = []
            for ext_name in REQUIRED_EXTENSIONS.keys():
                if not found_files[ext_name]:
                    missing.append(ext_name.upper())

            session_record = {
                "dataset": dataset_name,
                "patient_id": patient_id,
                "session": session_name,
                "folder_path": folder_path,
                "edf_count": len(found_files["edf"]),
                "xml_count": len(found_files["xml"]),
                "tsv_count": len(found_files["tsv"]),
                "json_count": len(found_files["json"]),
                "missing": missing,
                "total_files": len(all_files)
            }
            all_sessions_checked.append(session_record)

            if missing:
                print(f"    {session_name}: MISSING {', '.join(missing)}")
                all_issues.append({
                    "dataset": dataset_name,
                    "patient_id": patient_id,
                    "session": session_name,
                    "folder_path": folder_path,
                    "missing_edf": "YES" if "EDF" in missing else "",
                    "missing_xml": "YES" if "XML" in missing else "",
                    "missing_tsv": "YES" if "TSV" in missing else "",
                    "missing_json": "YES" if "JSON" in missing else "",
                    "edf_files": "; ".join(found_files["edf"]),
                    "xml_files": "; ".join(found_files["xml"]),
                    "tsv_files": "; ".join(found_files["tsv"]),
                    "json_files": "; ".join(found_files["json"])
                })
            else:
                print(f"    {session_name}: OK (EDF:{len(found_files['edf'])}, XML:{len(found_files['xml'])}, TSV:{len(found_files['tsv'])}, JSON:{len(found_files['json'])})")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total sessions checked: {len(all_sessions_checked)}")
    print(f"Sessions with missing files: {len(all_issues)}")

    # Count by missing type
    missing_edf = sum(1 for i in all_issues if i.get("missing_edf") == "YES")
    missing_xml = sum(1 for i in all_issues if i.get("missing_xml") == "YES")
    missing_tsv = sum(1 for i in all_issues if i.get("missing_tsv") == "YES")
    missing_json = sum(1 for i in all_issues if i.get("missing_json") == "YES")

    print(f"\nMissing file counts:")
    print(f"  - Missing EDF: {missing_edf}")
    print(f"  - Missing XML: {missing_xml}")
    print(f"  - Missing TSV: {missing_tsv}")
    print(f"  - Missing JSON: {missing_json}")

    # Save report
    if all_issues:
        with open(OUTPUT_REPORT, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ["dataset", "patient_id", "session", "folder_path",
                         "missing_edf", "missing_xml", "missing_tsv", "missing_json",
                         "edf_files", "xml_files", "tsv_files", "json_files"]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_issues)

        print(f"\nReport saved to: {OUTPUT_REPORT}")
    else:
        print("\nNo issues found - all sessions have required files!")

    return {"sessions_checked": all_sessions_checked, "issues": all_issues}


if __name__ == "__main__":
    check_session_files()
