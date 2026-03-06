# -*- mode: python; coding: utf-8 -*-
# Copyright 2026 David R DeBoer
# Licensed under the MIT license. See LICENSE file in the project root for details.


"""Some TLE handling tools"""

from importlib.metadata import version
__version__ = version('tle_ddtools')

EPOCH_FACTOR = 100.0
REMAP_S = ["name", "international_designator", "classification", "ephemeris_type"]
REMAP_TLE = {
    'line1': ["arcdoy", "arcmodf", "epochmodf", "mean_motion_dot", "mean_motion_ddot", "bstar", "element_set_number"],  # arcdoy/modf are extra fields for dating TLE archival dates
    'line2': ["inclination_deg", "raan_deg", "eccentricity", "argument_of_perigee_deg", "mean_anomaly_deg", "mean_motion_rev_per_day", "revolution_number_at_epoch"]
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