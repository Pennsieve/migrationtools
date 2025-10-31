#!/usr/bin/env python3
"""
Generate BIDS sessions.tsv sidecar files.
Creates sessions.tsv files for each patient/subject.
"""

from sidecar.SessionsTSV import SessionsTSV


def handle_sessions_tsv(patient_id, sessions_data, output_base_dir):
    """
    Generate sessions.tsv for a specific patient.

    Args:
        patient_id: Patient identifier (e.g., "4ZHY")
        sessions_data: List of dicts with 'age' for each session
        output_base_dir: Base output directory

    Returns:
        bool: True if successful, False otherwise
    """
    # Sort sessions by age
    sorted_sessions = sorted(sessions_data, key=lambda x: float(x['age']))

    # Create TSV rows
    rows = []
    for i, session in enumerate(sorted_sessions):
        age = float(session['age'])
        # Baseline only if it's the smallest age AND age is between 1.5 to 6 months
        if i == 0 and 1.5 <= age <= 6:
            visit_type = "baseline"
        else:
            visit_type = "followup"

        rows.append({
            "session": f"ses-visit{int(age)}m",
            "visit_type": visit_type,
            "age_in_months": age
        })

    # Calculate bids_path: PRV-{patient_id}/primary/sub-{patient_id}/
    bids_path = f"PRV-{patient_id}/primary/sub-{patient_id}/"

    # Create custom filename
    custom_filename = f"sub-{patient_id}_sessions.tsv"

    # Create sidecar
    sessions_sidecar = SessionsTSV(
        fields=rows,
        bids_path=bids_path,
        filename=custom_filename
    )

    # Validate and save
    try:
        if sessions_sidecar.validate():
            saved_path = sessions_sidecar.save(output_dir=output_base_dir)
            return True
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
