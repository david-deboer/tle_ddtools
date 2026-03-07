"""
Read in an npz file and generate a TLE file based on provided epoch.

Input record shape expected (per satnum):
{
  "name": Optional[str],
  "line1": str,          # optional (ignored for formatting)
  "line2": str,          # optional (ignored for formatting)
  "checksum_ok": Optional[bool],
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

"""
from . import S0, L1, L2
from .tle_utils import readdataz, epoch_doy_to_dt, epoch_dt_to_doy
from .tle_formatter import write_tles_to_file
from datetime import datetime, timedelta
from copy import copy


def tle_file_from_epoch(epoch_search, span_days=7.0, filename='concatz.npz', return_found=False, offset_warning=None):
    """
    Generate TLE files for all records in the given .npz file that have an epoch within span_days of epoch_search.
    epoch_search should be in the format YYDDD.DDDDDDDD or datetime

    """
    data = readdataz(filename, fmt=True)
    limits = data['lim']
    data = data['data']
    if isinstance(epoch_search, (float, str)):
        epoch_search_dt = epoch_doy_to_dt(epoch_search)
        epoch_search = float(epoch_search)
    elif isinstance(epoch_search, datetime):
        epoch_search_dt = epoch_search
        epoch_search = float(epoch_dt_to_doy(epoch_search_dt))
    else:
        raise ValueError("epoch_search must be a string, float, or datetime")
    span_timedelta = timedelta(days=span_days)
    print(f"Searching for TLEs with epoch within {span_days} days of {epoch_search_dt.isoformat()} : {limits[0]:.3f} to {limits[1]:.3f}")

    fnd = {}
    for satID, tle_dict in data.items():
        closest = {'delta': 1E10, 'key': None, 'archived': None}
        for epoch_key, tle_data in tle_dict.items():
            if epoch_key == 'S':
                continue
            archived_dt = epoch_doy_to_dt(tle_data[0][L1['arcdoy']])  # since read with fmt=True, this is the full archive datew as a float
            delta = abs((archived_dt - epoch_search_dt).total_seconds())
            if delta < closest['delta']:
                closest = {'delta': delta, 'key': epoch_key, 'archived': archived_dt}
        this_span = closest['archived'] - epoch_search_dt
        key = closest['key']
        offset_from_epoch = tle_dict[key][0][L2['revolution_number_at_epoch']] / tle_dict[key][1][L2['mean_motion_rev_per_day']]  # days
        if offset_warning is not None and offset_from_epoch > offset_warning:
            print(f"Note: offset from epoch is greater than {offset_warning} days: {offset_from_epoch:.2f}d")
        if abs(this_span) <= span_timedelta:
            print(f"Found {tle_dict['S'][S0['name']]} -- {satID} at {closest['archived'].isoformat()} ({this_span.total_seconds() / (3600):.3f}h)")
            tle_data = tle_dict[closest['key']]
            international_designator = {
                "year": tle_dict['S'][S0['international_designator']][0:2].strip(),
                "launch_number": tle_dict['S'][S0['international_designator']][2:5].strip(),
                "piece": tle_dict['S'][S0['international_designator']][5:8].strip()
            }
            fnd[satID] = {"name": tle_dict['S'][S0['name']],
                          "fields": {"satellite_number": satID,
                                     "international_designator": international_designator,
                                     "classification": tle_dict['S'][S0['classification']],
                                     "ephemeris_type": tle_dict['S'][S0['ephemeris_type']]
                                    }
                        }
            for k, i in L1.items():
                if k in ['arcdoy', 'arcmodf']:  # These are the extra ones.
                    continue
                if k == 'epochmodf':
                    fnd[satID]['fields']['epoch'] = f"{tle_data[0][i]:.8f}"
                elif k == 'element_set_number':
                    fnd[satID]['fields'][k] = int(tle_data[0][i])
                else:
                    fnd[satID]['fields'][k] = float(tle_data[0][i])
            for k, i in L2.items():
                fnd[satID]['fields'][k] = float(tle_data[1][i])
    if return_found:
        return fnd
    esr = f"{float(epoch_search):.3f}".replace('.', '_')
    fn = f"tle_{esr}.tle"
    print(f"Writing {len(fnd)} TLEs to {fn}")
    write_tles_to_file(fnd, fn)
    return fn

