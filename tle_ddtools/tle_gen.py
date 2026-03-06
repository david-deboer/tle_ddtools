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
REMAP_S = ["name", "international_designator", "classification", "ephemeris_type"]
REMAP_O = ['element_set_number']
REMAP_EPOCH = [
    ["epochmodf", "mean_motion_dot", "mean_motion_ddot", "bstar", "element_set_number", "inclination_deg"],  # last is actually line 2
    ["raan_deg", "eccentricity", "argument_of_perigee_deg", "mean_anomaly_deg", "mean_motion_rev_per_day", "revolution_number_at_epoch"]
    ]
"""
from . import REMAP_S, REMAP_EPOCH
from .tle_utils import readdataz, epoch_handle, parse_epoch
from .tle_formatter import write_tles_to_file
from datetime import timedelta


def tle_file_from_epoch(epoch_search, span_days=1.0, filename='concatz.npz', return_found=False, offset_warning=150.0):
    """
    Generate TLE files for all records in the given .npz file that have an epoch within span_days of epoch_search.
    epoch_search should be in the format YYDDD.DDDDDDDD.

    """
    data = readdataz(filename)
    limits = data['lim']
    data = data['data']
    epoch_search_dt = parse_epoch(epoch_search)
    span_timedelta = timedelta(days=span_days)
    sdict = {k: i for i, k in enumerate(REMAP_S)}
    line1 = {k: i for i, k in enumerate(REMAP_EPOCH[0])}
    line2 = {k: i for i, k in enumerate(REMAP_EPOCH[1])}
    print(f"Searching for TLEs with epoch within {span_days} days of {epoch_search} ({epoch_search_dt.isoformat()}) = {limits[0]:.3f} to {limits[1]:.3f}")

    fnd = {}
    for satID, tle_dict in data.items():
        closest = {'epoch': None, 'delta': 1E6, 'key': None}
        for epoch_key, tle_data in tle_dict.items():
            if epoch_key == 'S':
                continue
            this_epoch = epoch_handle('r', (epoch_key, tle_data[0][line1['epochmodf']]))
            delta = abs(float(this_epoch) - float(epoch_search))
            if delta < closest['delta']:
                closest = {'epoch': this_epoch, 'delta': delta, 'key': epoch_key}
        this_epoch_dt = parse_epoch(closest['epoch'])
        this_span = this_epoch_dt - epoch_search_dt
        offset_from_epoch = tle_data[0][line2['revolution_number_at_epoch']] / tle_data[1][line2['mean_motion_rev_per_day']]  # days
        if offset_from_epoch > offset_warning:
            print(f"Note: offset from epoch is greater than {offset_warning} days: {offset_from_epoch:.2f}d")
        if abs(this_span) <= span_timedelta:
            print(f"Found {satID} at {closest['epoch']:.4f} ({this_span.total_seconds() / (3600):.3f}h)")
            if 'S' not in tle_dict:
                print(f"Record for satID {satID} missing 'S' section, skipping.")
                continue
            tle_data = tle_dict[closest['key']]
            international_designator = {
                "year": tle_dict['S'][sdict['international_designator']][0:2].strip(),
                "launch_number": tle_dict['S'][sdict['international_designator']][2:5].strip(),
                "piece": tle_dict['S'][sdict['international_designator']][5:8].strip()
            }
            fnd[satID] = {"name": tle_dict['S'][sdict['name']],
                          "fields": {"satellite_number": satID,
                                     "international_designator": international_designator,
                                     "classification": tle_dict['S'][sdict['classification']],
                                     "ephemeris_type": tle_dict['S'][sdict['ephemeris_type']]
                                    }
                        }
            for k, i in line1.items():
                if k == 'epochmodf':
                    fnd[satID]['fields']['epoch'] = closest['epoch']
                elif k == 'element_set_number':
                    fnd[satID]['fields'][k] = int(tle_data[0][i])
                else:
                    fnd[satID]['fields'][k] = float(tle_data[0][i])
            for k, i in line2.items():
                fnd[satID]['fields'][k] = float(tle_data[1][i])
    if return_found:
        return fnd
    esr = f"{float(epoch_search):.3f}".replace('.', '_')
    fn = f"tle_{esr}.tle"
    print(f"Writing {len(fnd)} TLEs to {fn}")
    write_tles_to_file(fnd, fn)

