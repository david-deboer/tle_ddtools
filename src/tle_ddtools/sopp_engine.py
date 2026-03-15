
from sopp.sopp import Sopp
from sopp.config.builder import ConfigurationBuilder
from sopp.models.core import FrequencyRange
from sopp.filtering.presets import filter_name_regex, filter_name_does_not_contain, filter_orbit_is, filter_frequency, filter_name_contains
from sopp.models.ground.receiver import Receiver
from datetime import timedelta
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation
import astropy.units as u
from numpy import array
from argparse import Namespace


def main(start,
         duration_min,
         satname=None,
         tle_file='tle/active.tle',
         ra=None, dec=None,
         frequency_MHz=None,
         bandwidth_MHz=20.0,
         az_limit_deg=[-360, 360],
         el_limit_deg=0.0,
         ftype='horizon',
         orbit_type=None,
         exclude=False,
         contains='DTC',
         time_resolution_sec=2,
         beamwidth_deg=10.0,
         observatory="HCRO"):
    """
    Parameters
    ----------
    start : interpretable by astropy Time
        Time to start observation
    duration_min : float
        Duration in minutes
    satname : str or None
        If str, then only show this satellite and write it out
    tle_file : str
        Name of tle file to use
    ra : str or float  as recognized by SOPP
        If ftype == 'beam', RA of observation
    dec : str or float as recognized by SOPP
        If ftype == 'beam', declination of observation
    frequency : float
        Frequency in MHz
    bandwith : float
        Bandwidth in MHz
    az_limit : list of float
        Az limits in degrees
    el_limit : float
        Elevation limit in degrees
    ftype : str
        'horizon' or 'beam'
    orbit_type : str
        All, GEO, MEO, LEO, other
    exclude : str or False
        If str, only allow if string not in name
    contains : str or False
        If str, only allow if string is in name
    beamwidth_deg : float
        Desired size of beam FWHM in deg to include if ftype == 'beam'
    time_resolution : int
        Time resolution in seconds
    observatory : str, dict
        If str, use a known observatory, if dict use those parameters
        CURRENTLY IGNORED!!!

    """
    tracks = {}

    # Observation Window
    duration = timedelta(minutes=duration_min)
    starttime = Time(start).to_datetime()
    stoptime = starttime + duration
    config = (
        ConfigurationBuilder()
        .set_facility(
            latitude=40.8178049,
            longitude=-121.4695413,
            elevation=1019.0,
            name='HCRO',
            receiver=Receiver(beamwidth=beamwidth_deg)
        )
        .set_runtime_settings(
            concurrency_level=4,
            time_resolution_seconds=time_resolution_sec,
            min_altitude=el_limit_deg,
        )
        .set_time_window(
            begin=starttime,
            end=stoptime
        )
        .set_frequency_range(
            bandwidth=bandwidth_MHz,
            frequency=frequency_MHz
        )
        .set_observation_target(
            declination=ra,
            right_ascension=dec
        )
        .load_satellites(tle_file=tle_file)
        .add_filter(filter_frequency(FrequencyRange(bandwidth=bandwidth_MHz, frequency=frequency_MHz)))
        .add_filter(filter_name_regex(satname))
        .add_filter(filter_name_contains(contains))
        .add_filter(filter_name_does_not_contain(exclude))
        .add_filter(filter_orbit_is(orbit_type))
        .build()
    )
    location = EarthLocation(lat=config.reservation.facility.coordinates.latitude*u.deg,
                             lon=config.reservation.facility.coordinates.longitude*u.deg,
                             height=config.reservation.facility.elevation*u.m)
    # Determine Satellite Interference
    sopp = Sopp(config)

    events = sopp.get_satellites_above_horizon() if ftype == 'horizon' else sopp.get_satellites_crossing_main_beam()

    ########################################################################
    print(f'There are {len(events)} satellite interference events during {starttime.isoformat()} - {stoptime.isoformat()}')

    for i, window in enumerate(events, start=1):
        if len(window.azimuth) < 7:  # Too short to be of interest
            continue
        sat = Namespace(az=[], el=[], time=[], distance=[])

        # Get portions of track within az/el limits
        for j in range(len(window.azimuth)):
            if window.azimuth[j] < az_limit_deg[0] or window.azimuth[j] > az_limit_deg[1]:
                continue
            sat.az.append(window.azimuth[j])
            sat.el.append(window.altitude[j])
            sat.time.append(window.times[j])
            sat.distance.append(window.distance_km[j] * 1000.0)  # m

        srcname = window.satellite.name.replace(' ','').replace('[', '').replace(']', '').replace('-', '')
        sat.time = Time(sat.time, format='datetime')
        sat.az = array(sat.az) * u.deg
        sat.el = array(sat.el) * u.deg
        sat.distance = array(sat.distance) * u.m
        sky = SkyCoord(alt=sat.el, az=sat.az, obstime=sat.time, frame='altaz', location=location)
        sat.ra=sky.gcrs.ra
        sat.dec=sky.gcrs.dec
        tracks.setdefault(srcname, [])
        tracks[srcname].append(sat)

    return tracks