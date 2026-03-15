from datetime import datetime, timedelta
from math import modf
from . import EPOCH_FACTOR
from astropy.time import Time


def savedataz(data, filename='tle*.npz'):
    """
    Save TLE data (output of tle_parser.tlds_to_taz) to a taz file.

    """
    from numpy import savez, floor
    epoch_list = []
    for tle in data.values():
        for key in tle:
            if key == 'S':
                continue
            else:
                epoch_list.append(int(floor(key / EPOCH_FACTOR)))
    try:
        mind = min(epoch_list)
        maxd = max(epoch_list)
    except ValueError:
        print("No valid epochs found.")
        return
    print(f"{mind} - {maxd}")
    if '*' in filename:
        filename = filename.replace('*', f'{mind}_{maxd}')
    savez(filename, data=data, allow_pickle=True)
    print("Saved data to", filename)

def readdataz(filename):
    """
    Read TLE data from a taz file saved by savedataz.

    Parameters
    ----------
    filename : str
        The path to the taz file to read.

    """
    from numpy import load
    data = load(filename, allow_pickle=True)['data'].item()
    minarc, maxarc = float('inf'), float('-inf')
    for satID in data:
        for key in data[satID]:
            if key == 'S':
                continue
            else:
                newarc = tuple_to_epoch((data[satID][key][0][0], data[satID][key][0][1]))
                minarc = min(minarc, newarc)
                maxarc = max(maxarc, newarc)
    return {'lim': (mjd_to_dt(minarc), mjd_to_dt(maxarc)), 'data': data}


def get_times(key, entry):
    """
    Get the epoch times from a TLE entry, both the archived epoch and the TLE epoch.

    Returns:
        archived_epoch (mjd)
        tle_epoch (mjd)

    """
    tle_epoch = tuple_to_epoch((key, entry[0][TAZ_E['line1'].index('epochmodf')]))
    archived = tuple_to_epoch((entry[0][TAZ_E['line1'].index('arcmjdf')], entry[0][TAZ_E['line1'].index('arcmodf')]))
    return tle_epoch, archived


def epoch_to_tuple(epoch):
    """
    Splits the epoch/archive datetime/mjd/jd into the epoch key int and the remainder (modf)

    Parameter
    ----------
    epoch : float or tuple or datetime
        epoch value (datetime, jd, mjd)

    Returns
    -------
    tuple : modf and int parts of the epoch, scaled by EPOCH_FACTOR

    """
    if isinstance(epoch, datetime):
        epoch = dt_to_mjd(epoch)
    else:
        epoch = float(epoch)
        if epoch > 2400000.5:
            epoch = epoch - 2400000.5
    return modf(epoch * EPOCH_FACTOR)


def tuple_to_epoch(epoch_tuple):
    """
    Joins the scaled tuple of the key/remainder to produce the epoch value (scaled MJD)

    Parameters
    ----------
    epoch : tuple
        tuple of (integer part, fractional part) representing the scaled mjd and remainder

    Returns
    -------
    float : mjd value corresponding to the input scaled tuple

    """
    return (float(epoch_tuple[0]) + float(epoch_tuple[1])) / EPOCH_FACTOR


def dt_to_mjd(dt, scale='mjd'):
    """
    Convert a datetime to a Modified Julian Date (MJD).

    """
    T = Time(dt)
    v = float(T.mjd) if scale == 'mjd' else float(T.jd)
    return v
    # JD = 367 * Y - (7 * (Y + ((M + 9) // 12))) // 4 + (275 * M) // 9 + D + 1721013.5 + (h + m / 60 + s / 3600) / 24
    # MJD = JD - 2400000.5


def mjd_to_dt(mjd):
    """
    Convert a Modified Julian Date (MJD) to a datetime.

    """
    mjd = float(mjd)
    if mjd > 2400000.5:
        mjd = mjd - 2400000.5
    epoch = Time(mjd, format='mjd').to_datetime()
    return epoch


def doy_to_dt(epoch):
    """
    Parse epoch YYDDD.DDDDDDDD -> UTC datetime (naive).
    Convention: 57-99 => 1957-1999, 00-56 => 2000-2056.
    """
    t = str(epoch).strip()
    if len(t) < 5:
        raise ValueError(f"Bad epoch: {epoch!r}")

    yy = int(t[0:2])
    doy = int(t[2:5])
    frac = float("0" + t[5:]) if len(t) > 5 else 0.0

    year = 1900 + yy if yy >= 57 else 2000 + yy
    day0 = datetime(year, 1, 1) + timedelta(days=doy - 1)
    return day0 + timedelta(days=frac)


def dt_to_doy(epoch: datetime) -> float:
    """
    Convert a datetime to a TLE epoch YYDDD.ffffff.

    """
    doy = f"{epoch.strftime('%y')}{epoch.strftime('%j')}"
    sod = (epoch - datetime(epoch.year, epoch.month, epoch.day)).total_seconds()
    frac = f"{sod / 86400}"  # Convert seconds to fraction of a day
    return float(f"{doy}.{frac[2:]}")  # Remove '0' before the decimal point
