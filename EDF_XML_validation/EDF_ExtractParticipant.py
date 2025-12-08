import os

def extract_unique_participant_ids(directory):
    participant_ids = set()

    for filename in os.listdir(directory):
        if filename.lower().endswith(".edf") and filename.startswith("PRV-"):
            stem = filename[:-4]  # remove ".edf"
            parts = stem.split("-")

            if len(parts) >= 2:
                participant_id = parts[1]
                if len(participant_id) == 4:   # <-- enforce length 4
                    participant_ids.add(participant_id)

    return sorted(participant_ids)

# Example usage
directory_path = r"K:\PREVeNT files\EDF_Standerized"
unique_ids = extract_unique_participant_ids(directory_path)

print("Unique Participant IDs:")
for pid in unique_ids:
    print(pid)
