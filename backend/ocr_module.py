"""
Module 1 — OCR Extraction

Uses Tesseract OCR (via pytesseract) to read raw text off a document image,
then applies regex heuristics to pull out named fields.

Swap `extract_text` for a cloud OCR call (AWS Textract AnalyzeID, Azure AI
Document Intelligence prebuilt-idDocument model) for production-grade
accuracy on real passports/IDs — see README for details.
"""
import os
import re
import pytesseract
from PIL import Image, ImageOps, ImageFilter

# On Windows, pytesseract relies on the tesseract.exe being on PATH, which is
# a common source of "TesseractNotFoundError" even after installing it. Point
# straight at the default install location if PATH lookup would otherwise fail.
_WINDOWS_DEFAULT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
for _path in _WINDOWS_DEFAULT_PATHS:
    if os.path.exists(_path):
        pytesseract.pytesseract.tesseract_cmd = _path
        break


def extract_text(image: Image.Image) -> str:
    """Real ID/passport photos usually have busy security-pattern backgrounds
    that Tesseract reads poorly on their own. Grayscale + upscale + contrast
    + sharpen brings the printed text out from the background pattern before
    OCR runs, which makes a large practical difference."""
    image = image.convert("RGB")
    gray = ImageOps.grayscale(image)
    w, h = gray.size
    scale = max(1, min(3, 1600 // max(w, 1)))
    if scale > 1:
        gray = gray.resize((w * scale, h * scale), Image.LANCZOS)
    contrast = ImageOps.autocontrast(gray, cutoff=2)
    sharp = contrast.filter(ImageFilter.SHARPEN)
    return pytesseract.image_to_string(sharp, config="--psm 6")


def _mrz_date(s: str, prefer_past: bool) -> str:
    """Decode a 6-digit YYMMDD MRZ date field into a readable date."""
    if not re.fullmatch(r"\d{6}", s):
        return ""
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    from datetime import date
    current_year = date.today().year
    y2000, y1900 = 2000 + yy, 1900 + yy
    if prefer_past:
        # Birth dates: pick whichever century doesn't land in the future.
        year = y2000 if y2000 <= current_year else y1900
    else:
        # Expiry dates: MRZ-bearing documents only exist post-2000, so the
        # expiry year is always in the 2000s, whether already passed or not.
        year = y2000
    try:
        return date(year, mm, dd).strftime("%d %b %Y").upper()
    except ValueError:
        return f"{dd:02d}/{mm:02d}/{year}"


def _parse_mrz(line1: str, line2: str) -> dict:
    """Decode a standard TD3 (passport) 2-line, 44-char-per-line MRZ block."""
    line1 = line1.replace(" ", "").ljust(44, "<")[:44]
    line2 = line2.replace(" ", "").ljust(44, "<")[:44]

    name_field = line1[5:44]
    parts = name_field.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given = re.sub(r"\s+", " ", parts[1].replace("<", " ")).strip() if len(parts) > 1 else ""
    name = ", ".join(p for p in [surname, given] if p)

    return {
        "name": name,
        "passport_number": line2[0:9].rstrip("<"),
        "nationality": line2[10:13].replace("<", ""),
        "date_of_birth": _mrz_date(line2[13:19], prefer_past=True),
        "sex": line2[20] if line2[20] in ("M", "F") else "",
        "date_of_expiry": _mrz_date(line2[21:27], prefer_past=False),
    }


def _label_lookup(lines, label_patterns, value_pattern=None, pick="first") -> str:
    """Find a label line, then pull the value that follows it. Real ID cards
    often print two fields per row ('nationality ... card no.' then
    'Albanian 367253746' on the next line) — when value_pattern is given,
    it's used to pick just the matching token out of that combined line
    (a date, a single M/F letter, a digit run, a word) instead of returning
    the whole merged line. pick='last' grabs the final match instead of the
    first, for rows with two dates (issue date, then expiry date). Value
    patterns are matched case-sensitively on purpose (only the label search
    is case-insensitive) so e.g. an uppercase-only digit pattern doesn't
    accidentally match stray lowercase OCR noise."""
    for i, line in enumerate(lines):
        if any(re.search(p, line, re.IGNORECASE) for p in label_patterns):
            candidates = []
            m = re.search(r"[:\-]\s*(.+)$", line)
            if m and m.group(1).strip():
                candidates.append(m.group(1).strip())
            for nxt in lines[i + 1 : i + 3]:
                if nxt.strip() and not any(re.search(p, nxt, re.IGNORECASE) for p in label_patterns):
                    candidates.append(nxt.strip())
            for cand in candidates:
                if value_pattern:
                    matches = re.findall(value_pattern, cand)
                    if matches:
                        return (matches[-1] if pick == "last" else matches[0]).strip()
                elif cand:
                    return cand
    return ""


_DATE = r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"


def parse_fields(raw_text: str) -> dict:
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    joined = raw_text.replace("\n", " ")

    # Lines shaped like an MRZ (machine-readable zone) row
    mrz_lines = [l for l in lines if re.fullmatch(r"[A-Z0-9<]{20,44}", l.replace(" ", ""))]

    fields = {}
    if len(mrz_lines) >= 2:
        try:
            candidate = _parse_mrz(mrz_lines[-2], mrz_lines[-1])
            if re.fullmatch(r"[A-Z0-9]{6,9}", candidate.get("passport_number", "")):
                fields = candidate
        except Exception:
            fields = {}

    if not fields:
        # No usable MRZ (e.g. a national ID card) — read the bilingual field
        # labels directly, extracting just the value shape near each label
        # rather than trusting an entire (possibly two-column-merged) line.
        # \W* / [\s-]* between words tolerates OCR reading a space as a
        # hyphen or dropping it entirely ("date-of birth", "dateofbirth").
        def find(pattern):
            m = re.search(pattern, joined, re.IGNORECASE)
            return m.group(0).strip() if m else ""

        surname = _label_lookup(lines, [r"Surname"])
        given = _label_lookup(lines, [r"Given[\s-]*Name"])
        name = ", ".join(p for p in [surname, given] if p) or _label_lookup(lines, [r"\bName\b"])

        fields = {
            "name": name,
            "passport_number": (
                _label_lookup(lines, [r"Passport[\s-]*No", r"Card[\s-]*No"], value_pattern=r"[A-Z0-9]{6,12}")
                or _label_lookup(lines, [r"Passport[\s-]*No", r"Card[\s-]*No"], value_pattern=r"\d{6,12}")
                or find(r"\b[A-Z][0-9]{6,8}\b")
            ),
            "nationality": _label_lookup(lines, [r"Nationality"], value_pattern=r"[A-Za-z]{3,}(?:/[A-Za-z]{3,})?"),
            "date_of_birth": (
                _label_lookup(lines, [r"Date[\s-]*of[\s-]*Birth"], value_pattern=_DATE)
                or find(r"\b\d{1,2}\s?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s?\d{2,4}\b")
            ),
            "sex": _label_lookup(lines, [r"\bSex\b"], value_pattern=r"\b[MF]\b") or find(r"\b[MF]\b"),
            "date_of_expiry": _label_lookup(lines, [r"Date[\s-]*of[\s-]*Expiry"], value_pattern=_DATE, pick="last"),
        }

    fields["mrz_lines"] = mrz_lines
    return fields
