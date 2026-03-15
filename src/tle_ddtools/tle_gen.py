"""
Read in an npz file and generate a TLE file based on provided epoch.


"""
from . import S0
from .tle_utils import mjd_to_dt, readdataz, mjd_to_dt, dt_to_mjd, get_times
from .tle_parser import write_tlds_to_file, taz_to_tld
from datetime import datetime, timedelta



def tle_file_from_epoch(epoch_search, filename, span_days=7.0, return_found=False):
    """
    Generate TLE files for all records in the given taz file that have an epoch within span_days of epoch_search.

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
    
    """
    data = readdataz(filename)
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
    print(f"Searching for TLEs with epoch within {span_days} days of {epoch_search_dt.isoformat()} : {data['lim'][0]:.3f} to {data['lim'][1]:.3f}")

    fnd = {}
    for satID, tle_dict in data['data'].items():
        launch_year = int(tle_dict['S'][S0['intldesg']][0:2].strip())
        if launch_year < 50:
            launch_year += 2000
        else:
            launch_year += 1900
        if epoch_search_dt.year < launch_year:
            print(f"Skipping {tle_dict['S'][S0['name']]} -- {satID} because launch year {launch_year} is after search epoch {epoch_search_dt.year}")
            continue
        closest = {'delta': float('inf'), 'key': None, 'archived': None}
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
        if abs(this_span) <= span_timedelta:
            print(f"Found {tle_dict['S'][S0['name']]} -- {satID} at {closest['archived'].isoformat()} ({this_span.total_seconds() / (3600):.3f}h)")
            tle_data = tle_dict[closest['key']]
            fnd[satID] = taz_to_tle({satID: tle_dict}, closest['key'], satID=satID)[satID]

    if return_found:
        return fnd
    taz = f"{float(epoch_search):.3f}".replace('.', '_')
    fn = f"tle_{taz}.tle"
    print(f"Writing {len(fnd)} TLEs to {fn}")
    write_tlds_to_file(fnd, fn)
    return fn

