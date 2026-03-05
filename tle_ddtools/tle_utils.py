from datetime import datetime, timedelta
from math import modf
from numpy import array
from . import EPOCH_FACTOR

def savedataz(data, filename='tle*.npz'):
    """
    Save TLE data (output of tle_parser.remap) to a .npz file.

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
    Read TLE data from a .npz file saved by savedataz.

    """
    from numpy import load
    data = load(filename, allow_pickle=True)['data'].item()
    return data

def epoch_handle(cmd, epoch):
    """
    cmd = 'f'orward or 'r'everse
    forward takes the epoch_raw float and splits into the epoch key int and the remainder
    reverse takes a tuple of the key/remainder and produces the epoch value

    """
    if cmd[0].lower() == 'f':
        return modf(float(epoch) * EPOCH_FACTOR)
    if cmd[0].lower() == 'r':
        return (float(epoch[0]) + float(epoch[1])) / EPOCH_FACTOR
    raise ValueError("epoch handler command must be 'f'orward or 'r'everse")


def parse_epoch(epoch):
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


def make_epoch(epoch: datetime) -> float:
    """
    Convert a datetime to a TLE epoch YYDDD.ffffff.

    """
    doy = f"{epoch.strftime('%y')}{epoch.strftime('%j')}"
    sod = (epoch - datetime(epoch.year, epoch.month, epoch.day)).total_seconds()
    frac = f"{sod / 86400}"  # Convert seconds to fraction of a day
    return float(f"{doy}.{frac[2:]}")  # Remove '0' before the decimal point


def concatz(starter={}, base_dir='.', output_file='concatz.npz'):
    """
    Concatenate multiple .npz files into a single .npz file, merging data by satID and epoch keys.

    The data are added to the starter dict, which is then saved to output_file. The input files are expected to be in base_dir and match the pattern 'tle*.npz'.
     - Each input file should contain a dict of satIDs, where each satID maps to another dict of epoch keys (e.g., '2023-01-01T00:00:00') and their corresponding TLE data.
     - The function merges the TLE data for each satID across all files, ensuring that if the same epoch key exists in multiple files for the same satID, the last one read will take precedence.
     - The final merged data is saved to output_file in .npz format.
     - The function also prints a summary of the concatenation process, including the number of files processed and the number of unique satIDs in the final output.
     - Note: The starter dict can be used to provide an initial set of data that will be merged with the data from the input files. If not needed, it can be left as an empty dict.

    """
    from glob import glob
    from os.path import join
    from numpy import savez
    files = glob(join(base_dir, 'tle*.npz'))
    data = {}
    ctr = {}
    for f in sorted(files):
        print(f"Loading {f}")
        try:
            d = readdataz(f)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            continue
        for satID in d:
            data.setdefault(satID, {})
            ctr.setdefault(satID,[])
            for key, val in d[satID].items():
                data[satID][key] = val
                if key != 'S':
                    ctr[satID].append(key)
    for satID in data:
        starter.setdefault(satID, {})
        for key, val in data[satID].items():
            starter[satID][key] = val
    savez(output_file, data=starter, allow_pickle=True)
    print(f"Concatenated {len(files)} files into {output_file} with {len(starter)} unique satIDs")


def summary(filename='concatz.npz'):
    """
    Print a summary of the TLE data in the given .npz file, including the distribution of epoch counts per satID.
    """
    data = readdataz(filename)
    print(f"Summary of {filename}:")
    print(f"Total unique satIDs: {len(data)}")
    cnt_epochs = []
    list_epochs = []
    for satID, tle_dict in data.items():
        num_epochs = len([k for k in tle_dict if k != 'S'])
        cnt_epochs.append(num_epochs)
        list_epochs.extend([epoch_handle('r', (tle_dict[k][0][0], tle_dict[k][0][1])) for k in tle_dict if k != 'S'])
        # if num_epochs > 10:
        #     print(f"{tle_dict['S'][0]} ({satID}): {num_epochs} epochs")

    hist_epochs = list(range(min(cnt_epochs), max(cnt_epochs) + 1, 1))
    print(f"Average epochs per satID: {sum(cnt_epochs)/len(cnt_epochs):.2f} -- max {max(cnt_epochs)}")
    print("Epoch distribution:")
    for i in range(len(hist_epochs) - 1):
        count = sum(1 for n in cnt_epochs if hist_epochs[i] <= n < hist_epochs[i + 1])
        print(f"  {hist_epochs[i]}-{hist_epochs[i + 1]}: {count}")
    import matplotlib.pyplot as plt
    plt.hist(cnt_epochs, bins=hist_epochs, edgecolor='black')
    plt.title('Distribution of Epoch Counts per SatID')
    plt.xlabel('Number of Epochs')
    plt.ylabel('Count of SatIDs')
    # plt.xticks(hist_epochs)
    plt.grid(axis='y', alpha=0.75)
    plt.figure()
    y = list(range(len(list_epochs)))
    plt.plot(array(list_epochs)/1000, y, '.')
    plt.show()
    return list_epochs