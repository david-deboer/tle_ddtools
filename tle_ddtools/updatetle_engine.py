import requests
from bs4 import BeautifulSoup
from os import path
from . import tle_parser, EPOCH_FACTOR
from .tle_utils import make_epoch
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
    if archived is None:
        archived = make_epoch(datetime.now())
    series_rec = {}
    if group == '*':
        group = ''
    master_file = requests.get(base_url)
    soup = BeautifulSoup(master_file.text, 'html.parser')
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
            print(f"{td.text} - {tlefilename}:  {actual_href}")
            tle_url = path.join(base_url, actual_href)
            try:
                tle_file = requests.get(tle_url, timeout=20)
            except Exception as e:
                print(e)
                continue
            with open(tlefilename, 'w') as f:
                f.write(tle_file.text)
            data = tle_parser.remap(tle_parser.parse_tles_from_file(tlefilename, archived=archived))
            series_rec.update(data)
    return series_rec

def updatetle_dir(base_path='./tle', archived=None):
    if archived is None:
        archived = make_epoch(datetime.now())
    from os.path import join
    from glob import glob
    tle_files = glob(join(base_path, '*.tle'))
    series_rec = {}
    for f in tle_files:
        print(f"Parsing {f}")
        try:
            data = tle_parser.remap(tle_parser.parse_tles_from_file(f, archived=archived))
        except Exception as e:
            print(f"Error parsing {f}: {e}")
            continue
        series_rec.update(data)
    return series_rec

