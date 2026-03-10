# """
# tle_parser.py

# Clean, dependency-free TLE parser that supports:
# - Many TLEs in one input file (2-line or 3-line with optional name)
# - Output as a dictionary keyed by satellite number (NORAD catalog ID)

# """

# from __future__ import annotations

# from dataclasses import dataclass
# from typing import Any, Dict, List, Optional, Tuple
# from numpy import array, float32

# from . import REMAP_S, REMAP_TLE
# from .tle_utils import epoch_convert_fr_modf, epoch_doy_to_dt

# # =============================================================================
# # Public dataclass (optional convenience)
# # =============================================================================

# @dataclass(frozen=True)
# class TLE:
#     name: Optional[str]
#     line1: str
#     line2: str
#     archived: str | float
#     checksum_ok: Optional[bool]
#     fields: Dict[str, Any]


# # =============================================================================
# # Low-level helpers
# # =============================================================================

# def _checksum_expected(line: str) -> int:
#     """
#     TLE checksum: sum digits + 1 per '-' over columns 1-68, mod 10.
#     Checksum digit is column 69 (index 68).
#     """
#     s = 0
#     for ch in line[:68]:
#         if ch.isdigit():
#             s += int(ch)
#         elif ch == "-":
#             s += 1
#     return s % 10


# def _checksum_actual(line: str) -> Optional[int]:
#     if len(line) < 69:
#         return None
#     ch = line[68]
#     return int(ch) if ch.isdigit() else None


# def _parse_implied_decimal(field: str) -> float:
#     """
#     Parse TLE implied-decimal mantissa+exponent fields (8 chars), e.g.:
#       " 25020-3" => +0.25020e-3
#       "-11606-4" => -0.11606e-4
#     """
#     t = field.strip()
#     if not t:
#         raise ValueError("Empty implied-decimal field")

#     def try_split(k: int):
#         mant, exp = t[:-k], t[-k:]
#         if exp and exp[0] in "+-" and exp[1:].isdigit():
#             return mant, exp
#         return None

#     split = try_split(2) or try_split(3)
#     if not split:
#         raise ValueError(f"Bad implied-decimal field: {field!r}")

#     mant_str, exp_str = split
#     if mant_str in {"+", "-", ""}:
#         raise ValueError(f"Bad implied-decimal mantissa: {field!r}")

#     sign = -1.0 if mant_str[0] == "-" else 1.0
#     mant_digits = mant_str[1:] if mant_str[0] in "+-" else mant_str
#     if not mant_digits.isdigit():
#         raise ValueError(f"Bad implied-decimal digits: {field!r}")

#     mantissa = sign * (float(mant_digits) / 1e5)  # implied 0.xxxxx
#     exponent = int(exp_str)
#     return mantissa * (10.0 ** exponent)


# def _extract_templates(line1: str, line2: str, name: Optional[str]) -> Dict[str, Any]:
#     """
#     Store raw fixed-width slices (useful for exact-precision formatting later).
#     """
#     l1 = line1.rstrip("\n\r").ljust(69)
#     l2 = line2.rstrip("\n\r").ljust(69)
#     return {
#         "name": name,
#         "line1": {
#             "satellite_number": l1[2:7],
#             "classification": l1[7:8],
#             "int_desig_year": l1[9:11],
#             "int_desig_launch": l1[11:14],
#             "int_desig_piece": l1[14:17],
#             "epoch": l1[18:32],
#             "mean_motion_dot": l1[33:43],
#             "mean_motion_ddot": l1[44:52],
#             "bstar": l1[53:61],
#             "ephemeris_type": l1[62:63],
#             "element_set_number": l1[64:68],
#         },
#         "line2": {
#             "inclination_deg": l2[8:16],
#             "raan_deg": l2[17:25],
#             "eccentricity": l2[26:33],
#             "argument_of_perigee_deg": l2[34:42],
#             "mean_anomaly_deg": l2[43:51],
#             "mean_motion_rev_per_day": l2[52:63],
#             "revolution_number_at_epoch": l2[63:68],
#         },
#     }


# # =============================================================================
# # Splitting many TLE sets
# # =============================================================================

# def split_tle_sets(text: str) -> List[Tuple[Optional[str], str, str]]:
#     """
#     Split an input string into TLE sets.

#     Each returned item is: (name_or_None, line1, line2)

#     Supports:
#       - 2-line: 1..., 2...
#       - 3-line: name, 1..., 2...
#     Ignores blank lines.

#     Raises ValueError on malformed blocks.
#     """
#     lines = [ln.rstrip("\n\r") for ln in text.splitlines() if ln.strip()]
#     out: List[Tuple[Optional[str], str, str]] = []

#     i = 0
#     n = len(lines)
#     while i < n:
#         ln = lines[i]

#         # 2-line block
#         if ln.startswith("1 "):
#             if i + 1 >= n or not lines[i + 1].startswith("2 "):
#                 raise ValueError(f"Found line1 at input line {i+1} but next non-empty line is not line2")
#             out.append((None, lines[i], lines[i + 1]))
#             i += 2
#             continue

#         # 3-line block (name then 1/2)
#         if i + 2 < n and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
#             out.append((lines[i].strip(), lines[i + 1], lines[i + 2]))
#             i += 3
#             continue

#         raise ValueError(
#             f"Unrecognized TLE block starting at input line {i+1}: {ln!r}. "
#             "Expected '1 ...' or a name line followed by '1 ...' and '2 ...'."
#         )

#     return out


# # =============================================================================
# # Parsing one TLE (given name/lines)
# # =============================================================================

# def parse_tle_lines(
#     name: str,
#     line1: str,
#     line2: str,
#     archived: str | float,
#     *,
#     validate_checksum: bool = True,
# ) -> Dict[str, Any]:
#     """
#     Parse a single TLE given name (optional), line1, line2.

#     Returns a dict:
#       {
#         "name": Optional[str],
#         "line1": str,
#         "line2": str,
#         "checksum_ok": Optional[bool],
#         "fields": {... includes "_raw" templates ...}
#       }
#     """
#     if not line1.startswith("1 ") or not line2.startswith("2 "):
#         raise ValueError("Invalid TLE: expected line1 to start with '1 ' and line2 with '2 '")

#     l1 = line1.ljust(69)
#     l2 = line2.ljust(69)

#     checksum_ok: Optional[bool] = None
#     if validate_checksum:
#         a1, a2 = _checksum_actual(l1), _checksum_actual(l2)
#         e1, e2 = _checksum_expected(l1), _checksum_expected(l2)
#         checksum_ok = None if (a1 is None or a2 is None) else (a1 == e1 and a2 == e2)

#     # --- Line 1 (fixed columns) ---
#     satnum = int(l1[2:7])
#     classification = l1[7].strip() or None

#     int_desig_year = l1[9:11].strip() or None
#     int_desig_launch = l1[11:14].strip() or None
#     int_desig_piece = l1[14:17].strip() or None

#     epoch_raw = l1[18:32].strip()
#     epoch_dt = epoch_doy_to_dt(epoch_raw)

#     mean_motion_dot = float(l1[33:43].strip())
#     mean_motion_ddot = _parse_implied_decimal(l1[44:52])
#     bstar = _parse_implied_decimal(l1[53:61])

#     ephemeris_type = l1[62].strip() or None
#     element_set_number = int(l1[64:68].strip())

#     # --- Line 2 (fixed columns) ---
#     satnum2 = int(l2[2:7])
#     if satnum2 != satnum:
#         raise ValueError(f"Satellite number mismatch between lines: {satnum} vs {satnum2}")

#     inclination_deg = float(l2[8:16].strip())
#     raan_deg = float(l2[17:25].strip())

#     ecc_str = l2[26:33].strip()
#     if not ecc_str.isdigit():
#         raise ValueError(f"Bad eccentricity field: {ecc_str!r}")
#     eccentricity = float("0." + ecc_str)

#     argument_of_perigee_deg = float(l2[34:42].strip())
#     mean_anomaly_deg = float(l2[43:51].strip())
#     mean_motion_rev_per_day = float(l2[52:63].strip())
#     revolution_number_at_epoch = int(l2[63:68].strip())

#     fields: Dict[str, Any] = {
#         "satellite_number": satnum,
#         "classification": classification,
#         "international_designator": {
#             "year": int(int_desig_year) if (int_desig_year and int_desig_year.isdigit()) else int_desig_year,
#             "launch_number": int(int_desig_launch) if (int_desig_launch and int_desig_launch.isdigit()) else int_desig_launch,
#             "piece": int_desig_piece,
#         },
#         "epoch": {
#             "raw": epoch_raw,
#             "datetime_utc": epoch_dt,
#         },
#         "mean_motion_dot": mean_motion_dot,
#         "mean_motion_ddot": mean_motion_ddot,
#         "bstar": bstar,
#         "ephemeris_type": int(ephemeris_type) if (ephemeris_type and ephemeris_type.isdigit()) else ephemeris_type,
#         "element_set_number": element_set_number,
#         "inclination_deg": inclination_deg,
#         "raan_deg": raan_deg,
#         "eccentricity": eccentricity,
#         "argument_of_perigee_deg": argument_of_perigee_deg,
#         "mean_anomaly_deg": mean_anomaly_deg,
#         "mean_motion_rev_per_day": mean_motion_rev_per_day,
#         "revolution_number_at_epoch": revolution_number_at_epoch,
#     }

#     fields["_raw"] = _extract_templates(line1, line2, name)

#     return {
#         "name": name,
#         "line1": line1,
#         "line2": line2,
#         "checksum_ok": checksum_ok,
#         "archived": archived,
#         "fields": fields,
#     }


# # =============================================================================
# # Parsing many TLEs from file -> dict keyed by satellite number
# # =============================================================================

# def parse_tles(text: str, *, archived: str | float, validate_checksum: bool = True) -> Dict[int, Dict[str, Any]]:
#     """
#     Parse many TLE sets from a string.

#     Returns:
#       { satnum (int): parsed_tle_dict }

#     If the same satnum appears multiple times, the *last* occurrence wins.
#     """
#     out: Dict[int, Dict[str, Any]] = {}
#     for name, line1, line2 in split_tle_sets(text):
#         parsed = parse_tle_lines(name, line1, line2, archived, validate_checksum=validate_checksum)
#         satnum = int(parsed["fields"]["satellite_number"])
#         out[satnum] = parsed
#     return out


# def parse_tles_from_file(path: str, *, archived: str | float, validate_checksum: bool = True, encoding: str = "utf-8") -> Dict[int, Dict[str, Any]]:
#     """
#     Read a TLE file and parse all contained satellites.

#     Returns:
#       { satnum (int): parsed_tle_dict }
#     """
#     with open(path, "r", encoding=encoding) as f:
#         text = f.read()
#     return parse_tles(text, archived=archived, validate_checksum=validate_checksum)


# def parse_tles_as_dataclasses_from_file(path: str, *, archived: str | float, validate_checksum: bool = True, encoding: str = "utf-8") -> Dict[int, TLE]:
#     """
#     Read a TLE file and parse all contained satellites into dataclasses keyed by satnum.
#     """
#     with open(path, "r", encoding=encoding) as f:
#         text = f.read()

#     out: Dict[int, TLE] = {}
#     for name, line1, line2 in split_tle_sets(text):
#         d = parse_tle_lines(name, line1, line2, archived, validate_checksum=validate_checksum)
#         satnum = int(d["fields"]["satellite_number"])
#         out[satnum] = TLE(
#             name=d["name"],
#             line1=d["line1"],
#             line2=d["line2"],
#             archived=d["archived"],
#             checksum_ok=d["checksum_ok"],
#             fields=d["fields"],
#         )
#     return out


###############NEW STUFF BELOW USING SKYFIELD ##################
    # Line 1:
    #     satnum            (int)
    #     classification    (str)
    #     intldesg          (str)
    #     epochyr           (int, 2-digit)
    #     epochdays         (float)
    #     ndot              (rev/day^2)
    #     nddot             (rev/day^3)
    #     bstar             (float)
    #     ephtype           (int)
    #     elnum             (int)

    # Line 2:
    #     inclo             (deg)
    #     nodeo             (deg)
    #     ecco              (float)
    #     argpo             (deg)
    #     mo                (deg)
    #     no_kozai          (rev/day)
    #     revnum            (int)

# Initialize the record from orbital elements.

# Arguments of sgp4init (No keywords):
#     whichconst  - gravity constants (WGS72, WGS84, etc.)
#     opsmode     - operational mode ('a' = AFSPC, 'i' = improved)
#     satnum      - satellite number
#     epoch       - epoch time in days since 1949 December 31 00:00 UTC
#     bstar       - BSTAR drag term
#     ndot        - first time derivative of mean motion (rad/min^2)
#     nddot       - second time derivative of mean motion (rad/min^3)
#     ecco        - eccentricity
#     argpo       - argument of perigee (radians)
#     inclo       - inclination (radians)
#     mo          - mean anomaly (radians)
#     no_kozai    - mean motion (radians/minute)
#     nodeo       - right ascension of ascending node (radians)

from . import REMAP_S, REMAP_TLE
from .tle_utils import epoch_convert_fr_modf
from sgp4.api import Satrec, WGS72
from skyfield.api import EarthSatellite, load
from sgp4.exporter import export_tle
from numpy import array, float32

def TLE_from_EarthSatellite(sat):
    """
    Create a TLE string from a Skyfield EarthSatellite object, as given in EarthSatellite_from_dict() below.
 
    """
    line1, line2 = export_tle(sat.model)
    return f"{sat.name}\n{line1}\n{line2}\n"

def EarthSatellite_from_dict(sat):
    """
    Create a Skyfield EarthSatellite object from a dict of fields as given in one entry of
    the output of read_tle_files() below.  Needed to rewrite the TLE file.

    """
    satrec = Satrec()
    satrec.sgp4init(
        WGS72,            # WGS72
        'i',              # opsmode 'i' for improved accuracy (vs 'a' for old SGP4)
        sat['satnum'],      # satellite number (NORAD catalog ID)
        sat['epoch_jd'] - 2433281.5,    # Julian date epoch from 1949-12-31 00:00:00 UTC (SGP4 uses this offset)
        sat['bstar'],       # bstar drag term
        sat['ndot'],        # ndot (rev/day^2)
        sat['nddot'],       # nddot (rev/day^3)
        sat['ecco'],        # eccentricity
        sat['argpo'],       # argument of perigee (rad)
        sat['inclo'],       # inclination (rad)
        sat['mo'],          # mean anomaly (rad)
        sat['no_kozai'],    # mean motion (rev/day)
        sat['nodeo']        # right ascension of ascending node (rad)
    )
    satrec.classification = sat.get("classification", "U")
    satrec.intldesg = sat.get("intldesg", "")
    satrec.elnum = sat.get("elnum", 0)
    satrec.revnum = sat.get("revnum", 0)

    ts = load.timescale()
    esat = EarthSatellite.from_satrec(satrec, ts)
    esat.name = sat.get("name", "NULL")
    return esat

def read_tle_files(archived, tle_files='*.tle', base_path='./tle'):
    from os.path import join
    from glob import glob
    from skyfield.api import load as skyfield_load
    # Do help(Satrec)
    fields = {  # mapping from Skyfield Satrec field names to friendlier names, not used as a dict.
        # Line 1:
        'satnum': 'satellite_number',
        'classification': 'classification',
        'intldesg': 'international_designator',
        'epochyr': 'epochyr',
        'epochdays': 'epochdays',
        'ndot': 'mean_motion_dot',
        'nddot': 'mean_motion_ddot',
        'bstar': 'bstar',
        'ephtype': 'ephemeris_type',
        'elnum': 'element_set_number',
        # Line 2:
        'inclo': 'inclination_rad',
        'nodeo': 'raan_rad',
        'ecco': 'eccentricity',
        'argpo': 'argument_of_perigee_rad',
        'mo': 'mean_anomaly_rad',
        'no_kozai': 'mean_motion_rad_per_min',
        'revnum': 'revolution_number_at_epoch'
    }
    if isinstance(tle_files, str): 
        tle_files = glob(join(base_path, tle_files))
    sats = {}
    for f in tle_files:
        print(f"Reading {f}")
        this_data = skyfield_load.tle_file(f)
        for this_sat in this_data:
            # key = f"{this_sat.model.satnum}:{this_sat.model.intldesg}"
            key = this_sat.model.satnum  # Use satnum as key (NORAD catalog ID)
            sats[key] = {'name': this_sat.name, 'epoch_jd': float(this_sat.epoch.tt), 'archived': archived}
            for k, v in fields.items():
                sats[key][k] = getattr(this_sat.model, k)  # Keep the Skyfield field names
    return sats


def get_times(key, entry):
    """
    Get the epoch times from a TLE entry, both the archived epoch and the TLE epoch.

    Returns:
        archived_epoch (mjd)
        tle_epoch (mjd)

    """
    tle_epoch = epoch_convert_fr_modf('r', (key, entry[0][REMAP_TLE['line1'].index('epochmodf')]))
    archived = epoch_convert_fr_modf('r', (entry[0][REMAP_TLE['line1'].index('arcmjdf')], entry[0][REMAP_TLE['line1'].index('arcmodf')]))
    return tle_epoch, archived


def remap(sats):
    """
    Remap TLE data from read_tle_files() into a different structure that can track over time.

    See REMAP_S and REMAP_EPOCH for the specific fields included in "S" and the epoch_key arrays.
    The epoch_key is derived from the epoch by taking the integer part of (epoch * EPOCH_FACTOR), which allows grouping TLEs by epoch while retaining the fractional part in the array.

    """
    remapped = {}
    unk_ctr = 0
    for key, val in sats.items():
        if key in remapped:
            print(f"Warning:  satID {key} is duplicated")
        remapped[key] = {'S': []}
        for Skey in REMAP_S:  # Use loop to ensure correct order
            v = val.get(Skey)
            remapped[key]['S'].append(v)
        arcmodf, arcmjdf = epoch_convert_fr_modf('f', val['archived'])
        epochmodf, epoch_key = epoch_convert_fr_modf('f', val['epoch_jd'])
        lines = []
        for ll in sorted(REMAP_TLE.keys()):  # line1, line2
            aline = []
            for f in REMAP_TLE[ll]:
                if f == 'arcmjdf':
                    aline.append(arcmjdf)
                elif f == 'arcmodf':
                    aline.append(arcmodf)
                elif f == 'epochmodf':
                    aline.append(epochmodf)  # to get the epoch back use epoch_convert_fr_modf('r', [epochmodf, epoch_key])
                else:
                    aline.append(val[f])
            lines.append(aline)
        remapped[key][int(epoch_key)] = array(lines, dtype=float32)
    if unk_ctr:
        print(f"Unknown found: {unk_ctr}")
    return remapped

