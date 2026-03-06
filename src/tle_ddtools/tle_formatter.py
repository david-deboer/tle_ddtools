#!/usr/bin/env python3
"""
tle_formatter.py

Formatter that takes the output of tle_parser.parse_tles_from_file()
(a dict keyed by satellite number) and writes them back to a TLE text file.

IMPORTANT (per your request):
- This formatter does NOT use fields["_raw"] templates.
- It formats from the *actual numeric values* and does a best-effort canonical TLE layout.
- Checksums are recomputed.

Input record shape expected (per satnum):
{
  "name": Optional[str],
  "line1": str,          # optional (ignored for formatting)
  "line2": str,          # optional (ignored for formatting)
  "checksum_ok": Optional[bool],
  "archived": float/str  # epoch of archival
  "fields": {
      "satellite_number": int,
      "classification": Optional[str],
      "international_designator": {"year": int|str, "launch_number": int|str, "piece": str},
      "epoch": {"raw": "YYDDD.DDDDDDDD", "datetime_utc": datetime} OR "YYDDD.DDDDDDDD",
      "mean_motion_dot": float,
      "mean_motion_ddot": float,
      "bstar": float,
      "ephemeris_type": int|str|None,
      "element_set_number": int,
      "inclination_deg": float,
      "raan_deg": float,
      "eccentricity": float,
      "argument_of_perigee_deg": float,
      "mean_anomaly_deg": float,
      "mean_motion_rev_per_day": float,
      "revolution_number_at_epoch": int
  }
}

Library usage:
    from tle_parser import parse_tles_from_file
    from tle_formatter import write_tles_to_file

    tles = parse_tles_from_file("many.tle")
    write_tles_to_file(tles, "many_out.tle")

CLI usage (expects JSON keyed by satnum strings, values shaped like parser output):
    python tle_formatter.py --in many.json --out many_out.tle
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from math import floor, log10
from typing import Any, Dict, Optional, Union


# =============================================================================
# Checksum + slice helpers
# =============================================================================

def checksum_expected(line: str) -> int:
    """
    TLE checksum: sum digits + 1 per '-' over columns 1-68, mod 10.
    Checksum digit is column 69 (index 68).
    """
    s = 0
    for ch in line[:68]:
        if ch.isdigit():
            s += int(ch)
        elif ch == "-":
            s += 1
    return s % 10


def _set_slice(buf: list[str], start: int, end: int, value: str) -> None:
    """Write value into buf[start:end] (0-indexed, end-exclusive), padding/truncating."""
    width = end - start
    v = value[:width].ljust(width)
    for i, ch in enumerate(v):
        buf[start + i] = ch


# =============================================================================
# Epoch formatting
# =============================================================================

def _epoch_to_tle_14(epoch: Union[str, datetime, Dict[str, Any]]) -> str:
    """
    Return epoch as 'YYDDD.DDDDDDDD' (14 chars).
    Accepts:
      - already-formatted string
      - datetime
      - dict like {"raw": "..."} or {"datetime_utc": datetime}
    """
    if isinstance(epoch, str):
        t = epoch.strip()
        if len(t) != 14:
            raise ValueError(f"Epoch string must be 14 chars 'YYDDD.DDDDDDDD', got {t!r}")
        return t

    if isinstance(epoch, dict):
        if "raw" in epoch and isinstance(epoch["raw"], str):
            return _epoch_to_tle_14(epoch["raw"])
        if "datetime_utc" in epoch and isinstance(epoch["datetime_utc"], datetime):
            return _epoch_to_tle_14(epoch["datetime_utc"])
        raise ValueError("Epoch dict must contain 'raw' or 'datetime_utc'")

    if not isinstance(epoch, datetime):
        raise TypeError("epoch must be str, datetime, or epoch-dict")

    dt = epoch
    yy = dt.year % 100
    doy = int(dt.strftime("%j"))
    midnight = datetime(dt.year, dt.month, dt.day)
    frac = (dt - midnight).total_seconds() / 86400.0
    frac_str = f"{frac:.8f}"  # "0.xxxxxxxx"
    return f"{yy:02d}{doy:03d}{frac_str[1:]}"


# =============================================================================
# Canonical TLE numeric formatting (best-effort)
# =============================================================================

def _fmt_mean_motion_dot(value: float, decimals: int = 8) -> str:
    """
    Line 1 mean motion dot (cols 34-43, width 10) uses dot-leading style:
      positive: " .00013940"
      negative: "-.00013940"
    """
    sign = "-" if value < 0 else " "
    s = f"{abs(value):.{decimals}f}"     # "0.00013940"
    if not s.startswith("0."):
        # defensive; for typical values it's 0.xxx
        s = "0." + s.split(".", 1)[1]
    s = s[1:]                            # ".00013940"
    out = sign + s
    return out.rjust(10)[:10]


def _fmt_implied_decimal(value: float, width: int = 8) -> str:
    """
    TLE implied-decimal mantissa+exponent (typical width 8):
      ' 25020-3' means +0.25020e-3
    Uses 5-digit mantissa with implied decimal 0.mantissa and 1-digit exponent.

    This is best-effort canonical. If exponent magnitude exceeds 9, we raise.
    """
    if value == 0.0:
        return " 00000-0".rjust(width)[:width]

    sign_char = "-" if value < 0 else " "
    a = abs(value)

    exp = floor(log10(a)) + 1
    mant_int = int(round(a * 1e5 / (10 ** exp)))
    if mant_int >= 100000:
        mant_int //= 10
        exp += 1

    if exp < -9 or exp > 9:
        raise ValueError(f"Implied-decimal exponent out of range [-9,+9]: {exp} for value={value}")

    esign = "-" if exp < 0 else "+"
    out = f"{sign_char}{mant_int:05d}{esign}{abs(exp)}"
    return out.rjust(width)[:width]


def _fmt_deg(value: float, width: int = 8, decimals: int = 4) -> str:
    """Generic degrees fields (inc/raan/argp/ma): width 8, typically 4 decimals."""
    return f"{value:>{width}.{decimals}f}"[:width]


def _fmt_mean_motion(value: float, width: int = 11, decimals: int = 8) -> str:
    """Mean motion rev/day (line 2 cols 53-63): width 11, typically 8 decimals."""
    return f"{value:>{width}.{decimals}f}"[:width]


def _fmt_eccentricity(ecc: float) -> str:
    """Eccentricity is 7 digits, implied decimal point."""
    if ecc < 0 or ecc >= 1:
        raise ValueError(f"Eccentricity must be in [0,1), got {ecc}")
    n = int(round(ecc * 1e7))
    if n >= 10_000_000:
        n = 9_999_999
    return f"{n:07d}"


# =============================================================================
# Build one TLE from fields (best-effort canonical)
# =============================================================================

def tle_string_from_fields_best_effort(fields: Dict[str, Any], *, name: Optional[str] = None) -> str:
    """
    Create a TLE string from fields using canonical widths/precisions.
    Recomputes checksums.
    """
    satnum = int(fields["satellite_number"])
    classification = (fields.get("classification") or "U")
    if len(str(classification)) != 1:
        classification = str(classification)[:1]

    ides = fields.get("international_designator") or {}
    id_year = ides.get("year")
    id_launch = ides.get("launch_number")
    id_piece = ides.get("piece")

    if id_year is None or id_launch is None or id_piece is None:
        raise ValueError("international_designator must include year, launch_number, piece")

    yy = (int(id_year) % 100) if isinstance(id_year, int) else (int(str(id_year).strip()) % 100)
    launch = int(id_launch)
    piece = str(id_piece).strip()[:3]

    epoch_str = _epoch_to_tle_14(fields["epoch"])

    mm_dot = float(fields["mean_motion_dot"])
    mm_ddot = float(fields["mean_motion_ddot"])
    bstar = float(fields["bstar"])
    eph = fields.get("ephemeris_type", 0)
    eph_char = str(eph).strip()[:1] if eph is not None else "0"
    if eph_char == "":
        eph_char = "0"
    elset = int(fields["element_set_number"])

    inc = float(fields["inclination_deg"])
    raan = float(fields["raan_deg"])
    ecc = float(fields["eccentricity"])
    argp = float(fields["argument_of_perigee_deg"])
    ma = float(fields["mean_anomaly_deg"])
    mm = float(fields["mean_motion_rev_per_day"])
    rev = int(fields["revolution_number_at_epoch"])

    # ---- Line 1 buffer ----
    l1 = [" "] * 69
    _set_slice(l1, 0, 1, "1")
    _set_slice(l1, 1, 2, " ")
    _set_slice(l1, 2, 7, f"{satnum:05d}")
    _set_slice(l1, 7, 8, str(classification))
    _set_slice(l1, 8, 9, " ")
    _set_slice(l1, 9, 11, f"{yy:02d}")
    _set_slice(l1, 11, 14, f"{launch:03d}")
    _set_slice(l1, 14, 17, f"{piece:<3s}")
    _set_slice(l1, 17, 18, " ")
    _set_slice(l1, 18, 32, epoch_str)
    _set_slice(l1, 32, 33, " ")

    # mean motion dot (cols 34-43 => 33:43)
    _set_slice(l1, 33, 43, _fmt_mean_motion_dot(mm_dot, decimals=8))

    _set_slice(l1, 43, 44, " ")

    # mean motion ddot (cols 45-52 => 44:52)
    _set_slice(l1, 44, 52, _fmt_implied_decimal(mm_ddot, width=8))

    _set_slice(l1, 52, 53, " ")

    # bstar (cols 54-61 => 53:61)
    _set_slice(l1, 53, 61, _fmt_implied_decimal(bstar, width=8))

    _set_slice(l1, 61, 62, " ")
    _set_slice(l1, 62, 63, eph_char)
    _set_slice(l1, 63, 64, " ")
    _set_slice(l1, 64, 68, f"{elset:4d}")

    l1_no_ck = "".join(l1[:68]) + " "
    l1[68] = str(checksum_expected(l1_no_ck))
    line1 = "".join(l1)

    # ---- Line 2 buffer ----
    l2 = [" "] * 69
    _set_slice(l2, 0, 1, "2")
    _set_slice(l2, 1, 2, " ")
    _set_slice(l2, 2, 7, f"{satnum:05d}")
    _set_slice(l2, 7, 8, " ")
    _set_slice(l2, 8, 16, _fmt_deg(inc, width=8, decimals=4))
    _set_slice(l2, 16, 17, " ")
    _set_slice(l2, 17, 25, _fmt_deg(raan, width=8, decimals=4))
    _set_slice(l2, 25, 26, " ")
    _set_slice(l2, 26, 33, _fmt_eccentricity(ecc))
    _set_slice(l2, 33, 34, " ")
    _set_slice(l2, 34, 42, _fmt_deg(argp, width=8, decimals=4))
    _set_slice(l2, 42, 43, " ")
    _set_slice(l2, 43, 51, _fmt_deg(ma, width=8, decimals=4))
    _set_slice(l2, 51, 52, " ")
    _set_slice(l2, 52, 63, _fmt_mean_motion(mm, width=11, decimals=8))
    _set_slice(l2, 63, 68, f"{rev:5d}")

    l2_no_ck = "".join(l2[:68]) + " "
    l2[68] = str(checksum_expected(l2_no_ck))
    line2 = "".join(l2)

    if name:
        return f"{name}\n{line1}\n{line2}\n"
    return f"{line1}\n{line2}\n"


# =============================================================================
# Format many + write to file
# =============================================================================

def format_tles_best_effort(parsed_by_satnum: Dict[int, Dict[str, Any]], *, sort_by_satnum: bool = True) -> str:
    """
    Convert output of parse_tles_from_file() (dict keyed by satnum) into one TLE text blob.
    """
    items = parsed_by_satnum.items()
    if sort_by_satnum:
        items = sorted(items, key=lambda kv: kv[0])

    parts: list[str] = []
    for _, rec in items:
        fields = rec["fields"]
        nm = rec.get("name")
        parts.append(tle_string_from_fields_best_effort(fields, name=nm))
    return "".join(parts)


def write_tles_to_file(
    parsed_by_satnum: Dict[int, Dict[str, Any]],
    out_path: str,
    *,
    sort_by_satnum: bool = True,
    encoding: str = "utf-8",
) -> None:
    text = format_tles_best_effort(parsed_by_satnum, sort_by_satnum=sort_by_satnum)
    with open(out_path, "w", encoding=encoding) as f:
        f.write(text)


# =============================================================================
# CLI (expects JSON keyed by satnum strings)
# =============================================================================

def _cli() -> int:
    ap = argparse.ArgumentParser(description="Format parsed TLE JSON (keyed by satnum) back into TLE text (best-effort).")
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON file (keys are satnum strings).")
    ap.add_argument("--out", dest="out_path", required=True, help="Output TLE text file.")
    ap.add_argument("--no-sort", action="store_true", help="Do not sort by satellite number.")
    ap.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8).")
    args = ap.parse_args()

    with open(args.in_path, "r", encoding=args.encoding) as f:
        obj = json.load(f)

    parsed: Dict[int, Dict[str, Any]] = {int(k): v for k, v in obj.items()}
    write_tles_to_file(parsed, args.out_path, sort_by_satnum=(not args.no_sort), encoding=args.encoding)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
