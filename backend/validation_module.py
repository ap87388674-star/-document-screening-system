"""
Module 2 — Document Validation

Real ICAO 9303 MRZ checksum algorithm, expiry-date check, format check,
and a blacklist lookup (mocked against a local SQLite table — swap for
INTERPOL I-24/7 SLTD or a national document registry in production).
"""
import re
from datetime import datetime


def mrz_check_digit(s: str) -> int:
    weights = [7, 3, 1]

    def val(c):
        if c == "<":
            return 0
        if c.isdigit():
            return int(c)
        return ord(c.upper()) - 55  # A=10 ... Z=35

    return sum(val(c) * weights[i % 3] for i, c in enumerate(s)) % 10


def validate_document(fields: dict, blacklist: set) -> dict:
    flags = []
    fail_count = 0

    passport_no = fields.get("passport_number", "") or ""
    if re.fullmatch(r"[A-Z][0-9]{6,8}", passport_no):
        flags.append({"type": "ok", "message": "Passport number matches standard alphanumeric format."})
    else:
        flags.append({"type": "warn", "message": "Passport number format could not be confirmed from OCR output."})

    expiry_raw = fields.get("date_of_expiry", "") or ""
    year_match = re.search(r"(19|20)\d{2}", expiry_raw)
    if year_match:
        year = int(year_match.group(0))
        if year < datetime.now().year:
            flags.append({"type": "bad", "message": "Document expiry date is in the past — EXPIRED document."})
            fail_count += 1
        else:
            flags.append({"type": "ok", "message": f"Document valid until {year} — not expired."})
    else:
        flags.append({"type": "warn", "message": "Expiry date not clearly detected — flagged for manual check."})

    mrz_lines = fields.get("mrz_lines", [])
    if len(mrz_lines) >= 2:
        line2 = mrz_lines[-1].ljust(44, "<")[:44]
        doc_field = line2[:9]
        check_char = line2[9] if len(line2) > 9 else None
        expected = mrz_check_digit(doc_field)
        if check_char is not None and check_char.isdigit() and int(check_char) == expected:
            flags.append({"type": "ok", "message": "MRZ document-number checksum verified (ICAO 9303 algorithm)."})
        else:
            flags.append({"type": "bad", "message": "MRZ checksum mismatch — possible tampering in the machine-readable zone."})
            fail_count += 1
    else:
        flags.append({"type": "warn", "message": "No machine-readable zone detected to checksum — relying on visual fields only."})

    if passport_no and passport_no in blacklist:
        flags.append({"type": "bad", "message": f"Passport number {passport_no} matches an entry on the blacklist."})
        fail_count += 1
    elif passport_no:
        flags.append({"type": "ok", "message": "No match against the blacklist."})

    return {
        "flags": flags,
        "fail_count": fail_count,
        "validation_score": min(100, fail_count * 35),
    }
