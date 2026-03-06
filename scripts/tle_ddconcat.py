#! /usr/bin/env python3
from tle_ddtools import tle_utils
import argparse

ap = argparse.ArgumentParser(description="Concatenate TLE .npz files into a single file.")
ap.add_argument("-s", "--starter", help="Path to an existing .npz file to use as a starting point for concatenation, if any.", default={})
ap.add_argument("-o", "--output", help="Path to output .npz filename. Default is T{{E1}}_{{E2}}.npz located in directory with the data", default=None)
ap.add_argument("-d", "--directory", help="Directory to use for tle file search (and output if default).", default="./tle")
ap.add_argument("-g", "--glob", help="Glob pattern to match .npz files for concatenation.  Defaults to 'tle*.npz'.", default="tle*.npz")
ap.add_argument("-c", "--cleanup", help="If set, original .npz files will be deleted after concatenation. Use with caution!", action="store_true")
args = ap.parse_args()

tle_utils.concatz(starter=args.starter, output_file=args.output, base_dir=args.directory, globster=args.glob, cleanup=args.cleanup)
