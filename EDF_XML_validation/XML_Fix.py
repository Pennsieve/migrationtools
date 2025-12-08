import os
import re
import xml.etree.ElementTree as ET

# ---------- helpers ----------
def is_xml_readable(path):
    try:
        ET.parse(path)
        return True, None
    except ET.ParseError as e:
        return False, e


def fix_type_desc_line(line):
    """
    Fixes a single line containing type= or description= even if it's broken:
    - collapses doubled quotes:  ""foo"" -> "foo"
    - removes trailing extra quotes: "foo"" -> "foo"
    - replaces inner " with '
    - replaces & with "and"
    - replaces < with "less than" (and > with "greater than")
    """
    for attr in ("type", "description"):
        m = re.search(rf'\b{attr}\s*=\s*"', line)
        if not m:
            continue

        start = m.end()
        end = line.rfind('"')  # last quote on the line
        if end <= start:
            continue

        val = line[start:end]

        # strip boundary quotes if doubled/trailing
        val = val.strip('"')

        # your preferences
        val = val.replace("&", "and")
        val = val.replace("<", "less than").replace(">", "greater than")

        # inner quotes -> single quotes
        val = val.replace('"', "'")
        val = re.sub(r"''+", "'", val)  # collapse accidental doubled single-quotes

        # rebuild line with one clean attribute value
        line = line[:m.end()] + val + line[end:]

        # if there are still double quotes right after the value, collapse
        line = re.sub(rf'(\b{attr}\s*=\s*")([^"]*)""', r'\1\2"', line)

    return line


def sanitize_xml_text(xml_text):
    # 1) fix type/description line-by-line (handles embedded quotes)
    lines = xml_text.splitlines(True)
    fixed_text = "".join(fix_type_desc_line(ln) for ln in lines)

    # 2) specific global normalization you requested
    fixed_text = fixed_text.replace("6&4N", "6Y4N")

    # 3) fix OTHER attributes so XML is valid
    def fix_other_attrs(match):
        attr, val = match.group(1), match.group(2)

        if attr in ("type", "description"):
            return match.group(0)

        # keep XML valid and readable
        val = val.replace("<", "less than").replace(">", "greater than")

        # escape unescaped &
        val = re.sub(
            r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)',
            '&amp;',
            val
        )

        return f'{attr}="{val}"'

    fixed_text = re.sub(
        r'\b([A-Za-z_:\-][\w:.\-]*)\s*=\s*"([^"]*)"',
        fix_other_attrs,
        fixed_text
    )

    return fixed_text


def fix_only_bad_xmls(directory, out_dir=None, overwrite=False):
    """
    Fix only XML files that fail parsing.
    """
    if out_dir is None:
        out_dir = os.path.join(directory, "fixed_xml")
    os.makedirs(out_dir, exist_ok=True)

    fixed_files = []
    still_bad = []
    good_files = []

    for fn in os.listdir(directory):
        stem, ext = os.path.splitext(fn)
        if ext.lower() != ".xml" or not stem.endswith("-annotations"):
            continue

        in_path = os.path.join(directory, fn)
        ok, err = is_xml_readable(in_path)

        if ok:
            good_files.append(fn)
            continue

        # only fix if bad
        with open(in_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        fixed = sanitize_xml_text(raw)

        if overwrite:
            bak_path = in_path + ".bak"
            if not os.path.exists(bak_path):
                with open(bak_path, "w", encoding="utf-8") as bf:
                    bf.write(raw)
            out_path = in_path
        else:
            out_path = os.path.join(out_dir, fn)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fixed)

        ok2, err2 = is_xml_readable(out_path)
        if ok2:
            fixed_files.append(fn)
        else:
            still_bad.append((fn, str(err2)))

    return {
        "already_good": good_files,
        "fixed": fixed_files,
        "still_bad": still_bad,
        "out_dir": out_dir if not overwrite else directory
    }


# -------- example usage --------
if __name__ == "__main__":
    directory_path = r"K:\PREVeNT files\input"
    summary = fix_only_bad_xmls(directory_path, overwrite=False)

    print("Already good:", len(summary["already_good"]))
    print("Fixed:", len(summary["fixed"]))
    print("Still bad:", len(summary["still_bad"]))
    print("Fixed files saved in:", summary["out_dir"])

    if summary["still_bad"]:
        print("\nStill-bad files:")
        for fn, err in summary["still_bad"]:
            print(" ", fn, "->", err)
