from pathlib import Path
import shutil

# ==== Configure these two paths ====
SOURCE_DIR = Path(r"K:\PREVeNT files\EDF")  # e.g., r"K:\PREVeNT\raw_edf"
DEST_DIR   = Path(r"K:\PREVeNT files\EDF_Standerized")  # e.g., r"K:\PREVeNT\renamed_edf"
# ===================================

# Optional: set to True to preview actions without copying
DRY_RUN = False

def remove_institution_id(filename: str) -> str | None:
    """
    Given a filename like 'PRV-[InstitutionID]-[ParticipantID]-[Age]-[etc].edf',
    return 'PRV-[ParticipantID]-[Age]-[etc].edf'.
    If the name doesn't begin with the expected 'PRV-' pattern (case-insensitive),
    return None (caller can decide to skip).
    """
    # Work only on the name (without directory)
    name = filename

    # Separate stem and suffix to avoid issues with extra dots
    p = Path(name)
    stem, suffix = p.stem, p.suffix  # keep original case of suffix

    parts = stem.split('-')
    # Expect at least: ["PRV", "<Inst>", "<Participant>", ...]
    if len(parts) >= 3 and parts[0].upper() == "PRV":
        # Drop the institution id (parts[1])
        new_parts = [parts[0]] + parts[2:]
        new_name = "-".join(new_parts) + suffix
        return new_name

    # If it doesn't match, skip renaming by returning None
    return None

def unique_path(path: Path) -> Path:
    """
    If 'path' exists, append an incrementing suffix like '_dup1', '_dup2', ...
    to avoid overwriting.
    """
    if not path.exists():
        return path
    base = path.with_suffix("")  # remove .edf
    suffix = path.suffix
    i = 1
    while True:
        candidate = Path(f"{base}_dup{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def main():
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source not found: {SOURCE_DIR}")

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    copied, skipped, renamed = 0, 0, 0

    # Walk all files (including subfolders). If you only want top-level, use SOURCE_DIR.iterdir()
    for f in SOURCE_DIR.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() != ".edf":
            continue

        new_name = remove_institution_id(f.name)
        if new_name is None:
            # Not in PRV-* pattern; skip safely
            skipped += 1
            print(f"[SKIP] Not PRV pattern: {f.name}")
            continue

        dest_path = DEST_DIR / new_name
        dest_path = unique_path(dest_path)  # avoid collisions

        if DRY_RUN:
            print(f"[DRY RUN] Copy: {f}  ->  {dest_path}")
        else:
            shutil.copy2(f, dest_path)

        copied += 1
        if new_name != f.name:
            renamed += 1
            print(f"[OK] {f.name}  ->  {dest_path.name}")
        else:
            print(f"[OK] {f.name}  (no change)")

    print("\n=== Summary ===")
    print(f"Copied:   {copied}")
    print(f"Renamed:  {renamed}")
    print(f"Skipped:  {skipped}")
    print(f"From:     {SOURCE_DIR}")
    print(f"To:       {DEST_DIR}")

if __name__ == "__main__":
    main()

