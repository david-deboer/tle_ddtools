# -*- mode: python; coding: utf-8 -*-
# Copyright 2026 David R DeBoer
# Licensed under the MIT license. See LICENSE file in the project root for details.


"""Some TLE handling tools"""

from importlib.metadata import version
__version__ = version('tle_ddtools')

FIELDS = {  # mapping from Skyfield Satrec field names to friendlier names, not used as a dict.
    # Line 1:
    'satnum': 'satellite_number',
    'classification': 'classification',
    'intldesg': 'international_designator',
    'epochyr': 'epochyr',
    'epochdays': 'epochdays',
    'ndot': 'mean_motion_dot',
    'nddot': 'mean_motion_ddot',
    'bstar': 'bstar',
    'ephtype': 'ephemeris_type',
    'elnum': 'element_set_number',
    # Line 2:
    'inclo': 'inclination_rad',
    'nodeo': 'raan_rad',
    'ecco': 'eccentricity',
    'argpo': 'argument_of_perigee_rad',
    'mo': 'mean_anomaly_rad',
    'no_kozai': 'mean_motion_rad_per_min',
    'revnum': 'revolution_number_at_epoch'
}

EPOCH_FACTOR = 100.0
REMAP_S = ["name", "intldesg", "classification", "ephtype"]
REMAP_TLE = { # arcmjdf/modf are extra fields for dating TLE archival dates (see tle_parser docuemntation for details)
    'line1': ["arcmjdf", "arcmodf", "epochmodf", "ndot",    "nddot", "bstar",    "elnum"], 
    'line2': ["inclo",   "nodeo",   "ecco",       "argpo",  "mo",    "no_kozai", "revnum"]
}

S0 = {k: i for i, k in enumerate(REMAP_S)}
L1 = {k: i for i, k in enumerate(REMAP_TLE['line1'])}
L2 = {k: i for i, k in enumerate(REMAP_TLE['line2'])}

def return_ind(s):
    if s in S0:
        return S0[s]
    elif s in L1:
        return (0, L1[s])
    elif s in L2:
        return (1, L2[s])
    else:
        raise ValueError(f"Unknown field {s}")