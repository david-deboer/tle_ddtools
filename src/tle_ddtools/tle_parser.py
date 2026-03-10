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

from . import REMAP_S, REMAP_TLE, FIELDS
from .tle_utils import tuple_to_epoch, epoch_to_tuple
from sgp4.api import Satrec, WGS72
from skyfield.api import EarthSatellite, load
from sgp4.exporter import export_tle
from numpy import array, float32
from os.path import join


def write_tles_to_file(sats, filename='output.tle'):
    with open(filename, 'w') as f:
        for satnum, sat in sats.items():
            f.write(TLE_from_EarthSatellite(EarthSatellite_from_dict(sat)))


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

def read_tle_files(archived='now', tle_files='*.tle', base_path='./tle'):
    from glob import glob
    from skyfield.api import load as skyfield_load
    if archived == 'now':
        from datetime import datetime
        archived = datetime.now()
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
            for k, v in FIELDS.items():
                sats[key][k] = getattr(this_sat.model, k)  # Keep the Skyfield field names
    return sats


def get_times(key, entry):
    """
    Get the epoch times from a TLE entry, both the archived epoch and the TLE epoch.

    Returns:
        archived_epoch (mjd)
        tle_epoch (mjd)

    """
    tle_epoch = tuple_to_epoch((key, entry[0][REMAP_TLE['line1'].index('epochmodf')]))
    archived = tuple_to_epoch((entry[0][REMAP_TLE['line1'].index('arcmjdf')], entry[0][REMAP_TLE['line1'].index('arcmodf')]))
    return tle_epoch, archived

def npz_to_tle(data):
    """
    Remap input from an npz file to the format from the read_tle_files

    """
    remapped = {}

def tle_to_npz(sats):
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
        arcmodf, arcmjdf = epoch_to_tuple(val['archived'])
        epochmodf, epoch_key = epoch_to_tuple(val['epoch_jd'])
        lines = []
        for ll in sorted(REMAP_TLE.keys()):  # line1, line2
            aline = []
            for f in REMAP_TLE[ll]:
                if f == 'arcmjdf':
                    aline.append(arcmjdf)
                elif f == 'arcmodf':
                    aline.append(arcmodf)
                elif f == 'epochmodf':
                    aline.append(epochmodf)  # to get the epoch back use tuple_to_epoch([epochmodf, epoch_key])
                else:
                    aline.append(val[f])
            lines.append(aline)
        remapped[key][int(epoch_key)] = array(lines, dtype=float32)
    if unk_ctr:
        print(f"Unknown found: {unk_ctr}")
    return remapped

