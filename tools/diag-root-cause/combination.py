#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from typing import Any

CUR_DIR = os.fspath(os.path.dirname(__file__))
ALPHAS = [0.01, 0.02, 0.03, 0.04, 0.05]


def log(msg):
    print(msg, file=sys.stderr)


def run_diag(tsdr_file: str, out_dir: str, alpha: float, pc_stable: bool) -> Any:
    cmd = [
        f"{CUR_DIR}/diag.py", tsdr_file,
        '--citest-alpha', str(alpha),
        '--out-dir', out_dir,
    ]
    if pc_stable:
        cmd.append('--pc-stable')
    log('>> ' + ' '.join(cmd))
    proc = subprocess.run(
            ' '.join(cmd),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    log(proc.stdout.decode('utf-8'))
    log(proc.stderr.decode('utf-8'))
    if proc.returncode != 0:
        raise OSError('Raise an error of run_diag')
    return proc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tsdr_files",
                        nargs='+',
                        help="out directory")
    parser.add_argument("--out-dir", required=True, help="out directory")
    args = parser.parse_args()

    for tsdr_file in args.tsdr_files:
        for pc_stable in [True, False]:
            for alpha in ALPHAS:
                run_diag(tsdr_file, args.out_dir, alpha, pc_stable)


if __name__ == '__main__':
    main()
