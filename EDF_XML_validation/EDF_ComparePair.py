import os

def extract_unique_participant_ids(directory):
    participant_ids = set()

    for filename in os.listdir(directory):
        if filename.lower().endswith(".edf") and filename.startswith("PRV-"):
            stem = filename[:-4]  # remove ".edf"
            parts = stem.split("-")

            if len(parts) >= 2:
                participant_id = parts[1]
                if len(participant_id) == 4:
                    participant_ids.add(participant_id)

    return sorted(participant_ids)


def find_missing_edf_annotation_pairs(directory):
    edf_stems = set()
    annotation_stems = set()

    for filename in os.listdir(directory):
        lower = filename.lower()
        stem, ext = os.path.splitext(filename)

        if ext.lower() == ".edf":
            edf_stems.add(stem)

        elif ext.lower() == ".xml" and stem.endswith("-annotations"):
            base_stem = stem[:-len("-annotations")]  # remove suffix
            annotation_stems.add(base_stem)

    # Now compare base stems
    missing_annotations_for_edf = sorted(edf_stems - annotation_stems)
    missing_edf_for_annotations = sorted(annotation_stems - edf_stems)

    return missing_annotations_for_edf, missing_edf_for_annotations


# ---------------- Example usage ----------------
if __name__ == "__main__":
    directory_path = r"K:\PREVeNT files\EDF_Standerized"

    # 1) Unique Participant IDs
    unique_ids = extract_unique_participant_ids(directory_path)
    print("Unique Participant IDs (length=4):")
    for pid in unique_ids:
        print(pid)

    # 2) Missing EDF <-> annotations XML pairs
    missing_xml, missing_edf = find_missing_edf_annotation_pairs(directory_path)

    print("\nEDF files missing matching -annotations.xml:")
    for stem in missing_xml:
        print(stem + ".edf  --> missing " + stem + "-annotations.xml")

    print("\nAnnotations XML files missing matching EDF:")
    for stem in missing_edf:
        print(stem + "-annotations.xml  --> missing " + stem + ".edf")
