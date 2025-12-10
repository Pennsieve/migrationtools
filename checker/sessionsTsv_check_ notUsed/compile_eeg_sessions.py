'''
Compile sessions.tsv files from sessionstsv_matched/ to sessionstsv_compiled/
Each file is stored in a sub-<patient_id>/ folder structure.

Input: checker/output/sessionsTsv_check/sessionstsv_matched/sub-<patient_id>_sessions.tsv
Output: checker/output/sessionsTsv_check/sessionstsv_compiled/sub-<patient_id>/sub-<patient_id>_sessions.tsv
'''

import os
import re
import shutil
from pathlib import Path

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER_DIR = os.path.dirname(SCRIPT_DIR)
INPUT_DIR = os.path.join(CHECKER_DIR, "output", "sessionsTsv_check", "sessionstsv_matched")
OUTPUT_DIR = os.path.join(CHECKER_DIR, "output", "sessionsTsv_check", "sessionstsv_compiled")


def extract_patient_id_from_filename(filename):
    """Extract patient_id from filename like 'sub-<patient_id>_sessions.tsv'"""
    match = re.match(r'sub-(.+)_sessions\.tsv', filename)
    if match:
        return match.group(1)
    return None


def compile_sessions():
    """
    Compile sessions.tsv files from matched folder to compiled folder.
    Each file is stored in sub-<patient_id>/ folder structure.
    """
    print("=" * 80)
    print("Compiling sessions.tsv files")
    print("=" * 80)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory not found: {INPUT_DIR}")
        return

    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

    compiled = []
    errors = []

    for tsv_file in Path(INPUT_DIR).glob("sub-*_sessions.tsv"):
        patient_id = extract_patient_id_from_filename(tsv_file.name)

        if patient_id:
            # Create sub-<patient_id>/ folder
            dest_dir = Path(OUTPUT_DIR) / f"sub-{patient_id}"
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy file to destination
            dest_file = dest_dir / tsv_file.name
            shutil.copy2(tsv_file, dest_file)

            print(f"  {tsv_file.name} -> sub-{patient_id}/")
            compiled.append(str(dest_file))
        else:
            print(f"  Warning: Could not extract patient ID from {tsv_file.name}")
            errors.append(tsv_file.name)

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"  Files compiled: {len(compiled)}")
    if errors:
        print(f"  Errors: {len(errors)}")
        for e in errors:
            print(f"    - {e}")

    return {
        "compiled": compiled,
        "errors": errors
    }


if __name__ == "__main__":
    compile_sessions()
    print("\nScript completed.")
