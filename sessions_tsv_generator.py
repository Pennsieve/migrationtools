#!/usr/bin/env python3
"""
Generate BIDS sessions.tsv sidecar files.
Creates sessions.tsv files for each patient/subject.
"""

import csv
from pathlib import Path
from typing import Dict, Any

from sidecar.sessionsTSV import SessionsTSV

MASTER_MIGRATION_METADATA = "origin/metadata/metadata.csv"


def read_csv_to_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Convert CSV into a dictionary indexed by (patient_id, session_dir).
    Skips the first row and uses the second row as header.
    Returns: dict like {('1W4Y', 'ses-visit03m'): {...row data...}, ...}
    """
    data = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        # Skip the first row (category row)
        next(f)
        # Now use DictReader which will use the current line (second row) as header
        reader = csv.DictReader(f)
        for row in reader:
            # Use PID1 as patient_id and session as session_dir
            patient_id = row.get("PID1")
            session_dir = row.get("session")
            if not patient_id or not session_dir:
                continue
            # Use (patient_id, session_dir) as composite key
            key = (patient_id.strip(), session_dir.strip())
            data[key] = {k: v for k, v in row.items()}
    return data


def handle_sessions_tsv(patient_id, sessions_data, output_base_dir):
    """
    Generate sessions.tsv for a specific patient.

    Args:
        patient_id: Patient identifier (e.g., "4ZHY")
        sessions_data: List of dicts with 'session_dir' for each session
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """
    # Load CSV metadata
    csv_path = Path(__file__).parent / MASTER_MIGRATION_METADATA
    data_map = {}
    if csv_path.exists():
        try:
            data_map = read_csv_to_dict(csv_path)
        except Exception as e:
            print(f"    Warning: Error reading CSV: {e}")

    # Build session info from CSV data
    session_info_list = []
    for session in sessions_data:
        # Extract session name from session_dir path (e.g., "ses-visit24m")
        session_name = Path(session['session_dir']).name

        # Look up metadata for this patient/session
        patient_data = data_map.get((patient_id, session_name), {})

        # Get age from CSV (age_eeg_calc column), default to 0 if not found
        age_str = patient_data.get("age_eeg_calc", "0")
        try:
            age = float(age_str) if age_str else 0
        except ValueError:
            age = 0

        # Get visit type from CSV (Visit Type column), default based on age
        visit_type = patient_data.get("Visit Type", "").strip().lower()
        if not visit_type:
            # Default logic: baseline if age between 1.5-6 months
            visit_type = "baseline" if 1.5 <= age <= 6 else "followup"

        # Get sleep_captured from CSV (F11SLEEP column), default to "n/a"
        sleep_captured = patient_data.get("F11SLEEP", "n/a")
        if not sleep_captured:
            sleep_captured = "n/a"

        session_info_list.append({
            "session_name": session_name,
            "age": age,
            "visit_type": visit_type,
            "sleep_captured": sleep_captured
        })

    # Sort sessions by age
    sorted_sessions = sorted(session_info_list, key=lambda x: x['age'])

    # Create TSV rows
    rows = []
    for i, session in enumerate(sorted_sessions):
        # If visit_type wasn't in CSV, determine baseline by position
        visit_type = session['visit_type']
        if visit_type not in ["baseline", "followup"]:
            # First session with age 1.5-6 months is baseline
            if i == 0 and 1.5 <= session['age'] <= 6:
                visit_type = "baseline"
            else:
                visit_type = "followup"

        rows.append({
            "session_id": session['session_name'],
            "session_description": visit_type,
            "subject_age_months": session['age'],
            "sleep_captured": session['sleep_captured']
        })

    # Calculate bids_path: PREVeNT Trial {patient_id}/primary/sub-{patient_id}/
    bids_path = f"PREVeNT Trial {patient_id}/primary/sub-{patient_id}/"

    # Create custom filename
    bids_filename = f"sub-{patient_id}_sessions.tsv"

    # Create sidecar
    sessions_sidecar = SessionsTSV(
        fields=rows,
        bids_path=bids_path,
        filename=bids_filename
    )

    # Validate and save
    try:
        if sessions_sidecar.validate():
            saved_path = sessions_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
