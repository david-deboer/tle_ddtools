#! /usr/bin/env python3
from tle_ddtools.tle_utils import concatz
import argparse

ap = argparse.ArgumentParser(description="Concatenate TLE .npz files into a single file.")
ap.add_argument("-s", "--starter", help="Path to an existing .npz file to use as a starting point for concatenation, if any.", default={})
ap.add_argument("-o", "--output", help="Path to output .npz filename. Default is T{YYMMDD}_{YYMMDD}.npz located in directory with the data", default=None)
ap.add_argument("-d", "--directory", help="Directory to use for tle file search (and output if default).", default="./tle")
ap.add_argument("-g", "--glob", help="Glob pattern to match .npz files for concatenation.  Defaults to 'tle*.npz'.", default="tle*.npz")
ap.add_argument("--cleanup", help="If set, original .npz files will be deleted after concatenation. Use with caution!", action="store_true")
args = ap.parse_args()

concatz(starter=args.starter, output_file=args.output, base_dir=args.directory, globster=args.glob, cleanup=args.cleanup)
