import requests
from bs4 import BeautifulSoup
from os import path
from . import tle_parser, EPOCH_FACTOR
from .tle_utils import dt_to_mjd
from datetime import datetime


def make_tle_filename(tle_name):
    """
    Create a TLE filename from the TLE name.
    """
    tle_name = tle_name.strip()
    tle_name = tle_name.replace(' ', '_').replace('/', '_')
    tle_name = tle_name.replace('(', '').replace(')', '')
    tle_name = tle_name.replace("'", '').replace('"', '')
    tle_name = tle_name.replace(',', '').replace('.', '')
    tle_name = tle_name.replace('?', '').replace('!', '')
    tle_name = tle_name.replace('&', 'and')
    return f"{tle_name}.tle"


def updatetle_web(group='*', base_path='./tle', base_url='https://celestrak.org/NORAD/elements/', archived=None):
    """
    This pulls all of the TLE files from Celestrack and writes them to the base_path, then parses them and returns the data as a dict.
    If archived is provided, it will be used as the epoch for archiving the TLEs in the output data.  If archived is None, it will use the current time.

    Parameters
    ----------
    group : str, optional
        The group to search for in the Celestrak TLE files (default: '*', which matches all groups).
    base_path : str, optional
        The base path to save the TLE files to (default: './tle').
    base_url : str, optional
        The base URL to fetch the TLE files from (default: 'https://celestrak.org/NORAD/elements/').
    archived : datetime or None, optional
        The epoch to use for archiving the TLEs in the output data. If None, it will use the current time (default: None).
    """
    if archived is None:
        archived = dt_to_mjd(datetime.now())
    if group == '*':
        group = ''
    master_file = requests.get(base_url)
    soup = BeautifulSoup(master_file.text, 'html.parser')
    found_files = []
    for td in soup.find_all('td'):
        this_href = td.find('a')
        try:
            ttype = this_href.get('title')
        except AttributeError:
            continue
        if "debris" in td.text.lower() or "cesium" in td.text.lower():
            continue
        if ttype == 'TLE Data' and group in td.text:
            actual_href = this_href.get('href')
            groupname = actual_href.split('=')[1].split('&')[0]
            tlefilename = path.join(base_path, make_tle_filename(groupname))
            tle_url = path.join(base_url, actual_href)
            print(f"{td.text} - {tlefilename}:  {tle_url}")
            try:
                tle_file = requests.get(tle_url, timeout=20)
            except Exception as e:
                print(e)
                continue
            found_files.append(tlefilename)
            with open(tlefilename, 'w') as f:
                f.write(tle_file.text)
    return tle_parser.tles_to_taz(tle_parser.read_tle_files(archived=archived, tle_files=found_files, base_path=base_path))


def updatetle_dir(base_path='./tle', archived=None):
    """
    This reads all of the TLE files from the base_path, then parses them and returns the data as a dict.
    If archived is provided, it will be used as the epoch for archiving the TLEs in the output data.  If archived is None, it will use the current time.

    Parameters
    ----------
    base_path : str, optional
        The base path to read the TLE files from (default: './tle').
    archived : datetime or None, optional
        The epoch to use for archiving the TLEs in the output data. If None, it will use the current time (default: None).

    """
    if archived is None:
        archived = dt_to_mjd(datetime.now())
    from os.path import join
    from glob import glob
    tle_files = glob(join(base_path, '*.tle'))
    series_rec = {}
    for f in tle_files:
        print(f"Parsing {f}")
        try:
            data = tle_parser.tles_to_taz(tle_parser.read_tle_files(archived=archived, tle_files=f, base_path=base_path))
        except Exception as e:
            print(f"Error parsing {f}: {e}")
            continue
        series_rec.update(data)
    return series_rec

