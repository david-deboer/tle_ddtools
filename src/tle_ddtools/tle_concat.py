from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
from .tle_utils import readdataz, mjd_to_dt, tuple_to_epoch, get_times
from . import return_ind
from numpy import floor
from glob import glob
from os.path import join
from os.path import getsize
from datetime import datetime


def concatz(starter={}, output_file=None, base_dir='.', globster='tle*.npz', cleanup=False):
    """
    Concatenate multiple taz files into a single taz file, merging data by satID and epoch keys.

    All I/O is 'join'ed with base_dir.
    If 'starter' is a str, it will use the file contents as the starter.

    The data are added to the starter dict, which is then saved to output_file. The input files are expected to be in base_dir and match the pattern 'tle*.npz'.
     - Each input file should contain a dict of satIDs, where each satID maps to another dict of epoch keys (e.g., '2023-01-01T00:00:00') and their corresponding TLE data.
     - The function merges the TLE data for each satID across all files, ensuring that if the same epoch key exists in multiple files for the same satID, the last one read will take precedence.
     - The final merged data is saved to output_file in taz format.
     - The function also prints a summary of the concatenation process, including the number of files processed and the number of unique satIDs in the final output.
     - Note: The starter dict can be used to provide an initial set of data that will be merged with the data from the input files. If not needed, it can be left as an empty dict.

    """
    if isinstance(globster, str):
        files = glob(join(base_dir, globster))
    elif isinstance(globster, list):
        files = []
        for pattern in globster:
            files.extend(glob(join(base_dir, pattern)))
    else:
        raise ValueError("globster must be a string pattern or a list of file paths")
    data = {}
    limits = [datetime(year=2030, month=12, day=31), datetime(year=2020, month=1, day=1)]
    success = []
    maxsize = 0
    for f in sorted(files):
        print(f"Loading {f}")
        try:
            d = readdataz(f)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            continue
        success.append(f)
        maxsize = max(maxsize, getsize(f))
        limits = [min(limits[0], d['lim'][0]), max(limits[1], d['lim'][1])]
        d = d.get('data', {})
        for satID in d:
            data.setdefault(satID, {})
            for key, val in d[satID].items():
                data[satID][key] = val

    if starter:
        if isinstance(starter, str):
            from copy import copy
            starter_is_file = copy(starter)
            print(f"Loading starter from {starter}")
            try:
                d = readdataz(starter)
                limits = [min(limits[0], d['lim'][0]), max(limits[1], d['lim'][1])]
            except Exception as e:
                print(f"Error loading starter {starter}: {e}")
            starter = d.get('data', {})
        for satID in data:
            starter.setdefault(satID, {})
            for key, val in data[satID].items():
                starter[satID][key] = val
    else:
        starter = data
        starter_is_file = False

    # lower = mjd_to_dt(limits[0])
    lower = limits[0]
    lower = datetime(lower.year, lower.month, lower.day).strftime('%y%m%d')  # Round down to current day
    # upper = mjd_to_dt(limits[1]) + timedelta(days=1)
    upper = limits[1] + timedelta(days=1)
    upper = datetime(upper.year, upper.month, upper.day).strftime('%y%m%d')  # Round up to next day
    if output_file is None:
        output_file = join(base_dir, f"T{lower}_{upper}.npz")
    np.savez(output_file, data=starter, allow_pickle=True)
    print(f"Concatenated {len(files)} files into {output_file} onto previous {len(starter)} satIDs from {lower} - {upper}")
    if cleanup:
        if getsize(output_file) > maxsize:  # Only delete files if the output file size is bigger than the biggest, to avoid deleting everything in case of a bug
            from os import remove
            for f in success:
                print(f"Removing {f}")
                remove(f)
            if starter_is_file:
                from os.path import samefile
                if samefile(starter_is_file, output_file):
                    print(f"Starter file {starter_is_file} overwritten.")
                else:
                    print(f"Removing starter file {starter_is_file}")
                    remove(starter_is_file)
        else:
            print(f"Output file {output_file} is too small ({getsize(output_file)} bytes), skipping cleanup to avoid deleting everything in case of a bug.")


def analysis(filename, xkey='arc', ykey='epoch'):
    data = readdataz(filename)
    xy = [ [], [] ]
    keys = [xkey, ykey]
    for satID, tle_dict in data['data'].items():
        if len(tle_dict) < 3:
            continue
        x, y = [], []
        for epok, entry in tle_dict.items():
            if epok == 'S':
                continue
            e, a = get_times(epok, entry)
            for i in [0, 1]:
                if keys[i] == 'arc':
                    xy[i] = a
                elif keys[i] == 'epoch':
                    xy[i] = e
                else:
                    ind = return_ind(keys[i])
                    xy[i] = entry[ind[0]][ind[1]]
            x.append(xy[0])
            y.append(xy[1])
        plt.plot(x, y, '.')



def summary(filename):
    """Print/plot a summary of the TLE data in the given taz file."""
    data = readdataz(filename)
    print(f"Summary of {filename}:")
    print(f"Total unique satIDs: {len(data['data'])}")
    print("Epoch limits:", [x.isoformat() for x in data['lim']])
    list_epochs = []
    archive_mjd_counter = {}
    for satID, tle_dict in data['data'].items():
        archived = [tuple_to_epoch((tle_dict[k][0][0], tle_dict[k][0][1])) for k in tle_dict if k != 'S']
        list_epochs.extend(archived)
        for entry in archived:
            key = int(floor(entry))
            archive_mjd_counter.setdefault(key, 0)
            archive_mjd_counter[key] += 1

    sorted_archive_mjd = sorted(archive_mjd_counter.keys())
    archive_counter = {mjd_to_dt(key): archive_mjd_counter[key] for key in sorted_archive_mjd}
    keys = list(archive_counter.keys())

    # Choose bins: either an int (# of bins) or explicit edges (array)
    bdays = 7
    bins = int((list_epochs[-1] - list_epochs[0]) / bdays) + 1

    counts, edges = np.histogram(list_epochs, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    dt_centers = [mjd_to_dt(epoch) for epoch in centers]
    widths = np.diff(edges)

    cadence = [(keys[i], float(epoch)) for i, epoch in enumerate(np.diff(sorted_archive_mjd))]
    arc_date, arc_cadence = [], []
    for entry in cadence:
        arc_date.append(entry[0])
        arc_cadence.append(entry[1])

    # Plots
    plt.bar(dt_centers, counts, width=widths, align="center")
    plt.plot(archive_counter.keys(), archive_counter.values(), 'k.', label='Count per archived day')
    plt.xlabel("Archived Date")
    plt.ylabel(f"Count per {bdays} days (blue) / count per archived day (black)")
    plt.tight_layout()
    plt.show()

    plt.figure()
    plt.plot(arc_date, arc_cadence, '.')
    plt.xlabel("Archived Date")
    plt.ylabel("Cadence (days)")
    plt.tight_layout()
    plt.show()


