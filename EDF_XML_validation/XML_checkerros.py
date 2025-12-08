# import os
# import xml.etree.ElementTree as ET

# def check_xml_readability(directory):
#     readable = []
#     unreadable = []  # list of (filename, error)

#     for filename in os.listdir(directory):
#         stem, ext = os.path.splitext(filename)
#         if ext.lower() == ".xml" and stem.endswith("-annotations"):
#             path = os.path.join(directory, filename)
#             try:
#                 ET.parse(path)   # try parsing
#                 readable.append(filename)
#             except Exception as e:
#                 unreadable.append((filename, str(e)))

#     return readable, unreadable


# # ---------------- Example usage ----------------
# if __name__ == "__main__":
#     directory_path = r"K:\PREVeNT files\input"

#     readable, unreadable = check_xml_readability(directory_path)

#     print(f"Readable XML files: {len(readable)}")
#     for f in readable:
#         print("  OK:", f)

#     print(f"\nUnreadable XML files: {len(unreadable)}")
#     for f, err in unreadable:
#         print("  BAD:", f)
#         print("     Error:", err)

import os
import xml.etree.ElementTree as ET

def show_xml_error_context(path, context_lines=3):
    try:
        ET.parse(path)
        return True  # readable
    except ET.ParseError as e:
        line, col = e.position
        print(f"\nBAD: {os.path.basename(path)}")
        print(f"  Error: {e}")
        print(f"  At line {line}, column {col}\n")

        # Show surrounding lines
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)

        for i in range(start, end):
            prefix = ">>" if (i + 1) == line else "  "
            print(f"{prefix} L{i+1}: {lines[i].rstrip()}")

        return False


def scan_directory_for_bad_xml(directory):
    bad_files = []
    for fn in os.listdir(directory):
        stem, ext = os.path.splitext(fn)
        if ext.lower() == ".xml" and stem.endswith("-annotations"):
            path = os.path.join(directory, fn)
            ok = show_xml_error_context(path)
            if not ok:
                bad_files.append(path)
    return bad_files


# Example usage
directory_path = r"K:\PREVeNT files\input"
bad_files = scan_directory_for_bad_xml(directory_path)

print(f"\nTotal bad XML files: {len(bad_files)}")
