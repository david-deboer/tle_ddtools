"""
Read in an npz file and generate a TLE file based on provided epoch.


"""
from . import S0, L1, L2
from .tle_utils import mjd_to_dt, readdataz, mjd_to_dt, dt_to_mjd
from .tle_parser import get_times, write_tles_to_file, npzs_to_tle
from datetime import datetime, timedelta



def tle_file_from_epoch(epoch_search, filename, span_days=7.0, return_found=False, offset_warning=None):
    """
    Generate TLE files for all records in the given .npz file that have an epoch within span_days of epoch_search.
    epoch_search should be in the 

    Parameters
    ----------
    epoch_search : str, float, or datetime
        The epoch to search for, as a datetime object, a float (JD/MJD), or a string that can be parsed as a datetime.isoformat() or JD/MJD.
    filename : str
        The path to the .npz file containing the TLE data, as saved by savedataz.
    span_days : float, optional
        The number of days around epoch_search to include in the output TLE file (default: 7.0).
    return_found : bool, optional
        If True, return a dict of the found TLEs instead of writing to a file (default: False).
    offset_warning : float, optional
        If provided, print a warning if the offset from the epoch is greater than this number of days (default: None).
    
    """
    data = readdataz(filename)
    limits = data['lim']
    data = data['data']
    if isinstance(epoch_search, (float, str)):
        try:
            epoch_search = float(epoch_search)
            epoch_search = epoch_search if epoch_search < 2400000.5 else epoch_search - 2400000.5
            epoch_search_dt = mjd_to_dt(epoch_search)
        except ValueError:
            try:
                epoch_search_dt = datetime.fromisoformat(epoch_search)
                epoch_search = dt_to_mjd(epoch_search_dt)
            except ValueError:
                raise ValueError("epoch_search string must be parseable as a float (JD/MJD) or datetime.isoformat()")
    elif isinstance(epoch_search, datetime):
        epoch_search_dt = epoch_search
        epoch_search = dt_to_mjd(epoch_search_dt)
    else:
        raise ValueError("epoch_search must be a datetime, float, or string parseable as datetime or float")

    span_timedelta = timedelta(days=span_days)
    print(f"Searching for TLEs with epoch within {span_days} days of {epoch_search_dt.isoformat()} : {limits[0]:.3f} to {limits[1]:.3f}")

    fnd = {}
    for satID, tle_dict in data.items():
        launch_year = int(tle_dict['S'][S0['intldesg']][0:2].strip())
        if launch_year < 50:
            launch_year += 2000
        else:
            launch_year += 1900
        if epoch_search_dt.year < launch_year:
            print(f"Skipping {tle_dict['S'][S0['name']]} -- {satID} because launch year {launch_year} is after search epoch {epoch_search_dt.year}")
            continue
        closest = {'delta': 1E10, 'key': None, 'archived': None}
        for epoch_key, tle_data in tle_dict.items():
            if epoch_key == 'S':
                continue
            tle_epoch, archived = get_times(epoch_key, tle_data)
            archived_dt = mjd_to_dt(archived)
            delta = abs((archived_dt - epoch_search_dt).total_seconds())
            if delta < closest['delta']:
                closest = {'delta': delta, 'key': epoch_key, 'archived': archived_dt}
        this_span = closest['archived'] - epoch_search_dt
        key = closest['key']
        #offset_from_epoch = tle_dict[key][0][L2['revolution_number_at_epoch']] / tle_dict[key][1][L2['mean_motion_rev_per_day']]  # days
        #if offset_warning is not None and offset_from_epoch > offset_warning:
        #    print(f"Note: offset from epoch is greater than {offset_warning} days: {offset_from_epoch:.2f}d")
        if abs(this_span) <= span_timedelta:
            print(f"Found {tle_dict['S'][S0['name']]} -- {satID} at {closest['archived'].isoformat()} ({this_span.total_seconds() / (3600):.3f}h)")
            tle_data = tle_dict[closest['key']]
            fnd[satID] = npzs_to_tle({satID: tle_dict}, closest['key'], satID=satID)[satID]

    if return_found:
        return fnd
    esr = f"{float(epoch_search):.3f}".replace('.', '_')
    fn = f"tle_{esr}.tle"
    print(f"Writing {len(fnd)} TLEs to {fn}")
    write_tles_to_file(fnd, fn)
    return fn

