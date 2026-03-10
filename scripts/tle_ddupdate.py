#! /usr/bin/env python
from tle_ddtools import updatetle as utle
from tle_ddtools.tle_utils import savedataz
import argparse
from os.path import join


"""
This is currently a mess with the conflicted implementation of archived etc...

"""


CELESTRAK_URL = 'https://celestrak.org/NORAD/elements/'

ap = argparse.ArgumentParser()
ap.add_argument('group', help="Group to update TLEs for (default: *)", nargs='?', default='*')
ap.add_argument('--base-url', dest='base_url', help="Base url for tles",
                default=CELESTRAK_URL)  # set to anything, e.g. 'x', to avoid web fetching and just read from local directory
ap.add_argument('--base-path', dest='base_path', help="Base path for tles",
                default='./tle')
ap.add_argument('--archived', dest='archived', help="Epoch to use for archiving TLEs (default: now)", default='now')
ap.add_argument('--ident', dest='ident', help="DEPRECATED - Identifier in the one-off script", default=None)
args = ap.parse_args()

if args.ident is not None:
    filename = f"tle_{args.ident}.npz"
    args.archived = None
    print("Warning: --ident is deprecated and should not be used. This is a one-off script, so the filename will be based on the archived date instead.")
elif args.archived is not None:
    from datetime import datetime
    if args.archived == 'now':
        archived_epoch = datetime.now()
        filename = join(args.base_path, f"tle_{archived_epoch.strftime('%Y-%m-%dT%H:%M:%S')}.npz")
    else:
        raise NotImplementedError("Only 'now' is implemented for --archived argument at this time. THIS SCRIPT IS A MESS")
else:
    raise ValueError("Either --ident or --archived must be provided. --ident is deprecated, so please use --archived with 'now'.  THIS SCRIPT IS A MESS")

if args.base_url.startswith('http'):
    print(f"Updating TLEs for group {args.group} from {args.base_url} to {args.base_path}")
    data = utle.updatetle_web(group=args.group, base_path=args.base_path, base_url=args.base_url, archived=archived_epoch)
else:
    print(f"Updating TLEs for group {args.group} from {args.base_path}")
    data = utle.updatetle_dir(base_path=args.base_path, archived=archived_epoch)


print("Saving data to", filename)
savedataz(data, filename=filename)