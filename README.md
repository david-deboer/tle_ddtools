TLE DDTOOLS

There are two file formats and two corresponding code formats:

1:  TLE file - two-line dict (tld)
The TLE file is the standard TLE file from e.g. Celestrak
The tld internal format is:
    {satID: {'name': <>,
            'intldesg': <>,
            'epoch_jd': <>,
            'archived': <>,
            'ndot': <>,
            'nddot': <>,
            'bstar': <>,
            'ephtype': <>,
            'elnum': <>,
            'inclo': <>,
            'nodeo': <>,
            'ecco': <>,
            'argpo': <>,
            'mo', : <>,
            'no_kozai': <>,
            'revnum': <>
            }}

2:  npz file - tle-archive-zip (taz)
The npz file is the formatted npz fle
The TLE archive npz (TAZ) structure is:
    NORAD_ID_INT: 
    {
        'S': {<TAZ_S>},
        <EPOCH1_INT>: [<TAZ_E>['line1'],['line2']],  # Stored as float32
        <EPOCH2_INT>: [ " ], ...
    }

    EPOCHN is int(floor(EPOCH_FACTOR * epoch_mjd))  epochmodf is the fractional part of EPOCHN
    arcmodf, arcmjdf = modf(EPOCH_FACTOR * archived_mjd)