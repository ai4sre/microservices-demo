#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

import diag

CUR_DIR = os.fspath(os.path.dirname(__file__))
ALPHAS = [0.01, 0.02, 0.03, 0.04, 0.05]


def log(msg):
    print(msg, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tsdr_files",
                        nargs='+',
                        help="out directory")
    parser.add_argument("--out-dir", required=True, help="out directory")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dir = os.path.join(args.out_dir, ts)
    os.makedirs(dir)

    for tsdr_file in args.tsdr_files:
        for pc_stable in [True, False]:
            for alpha in ALPHAS:
                try:
                    diag.diag(tsdr_file, alpha, pc_stable, dir)
                except ValueError as e:
                    log(e)


if __name__ == '__main__':
    main()
