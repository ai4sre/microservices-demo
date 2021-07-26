#!/usr/bin/env python3
# %%
import argparse
import os
import subprocess
import sys
from typing import Any

CUR_DIR = os.fspath(os.path.dirname(__file__))
ALPHAS = [0.01, 0.02, 0.03, 0.04, 0.05]
DOCKER_DIAG = "docker-compose run --rm -v /tmp:/tmp/ diag"


def log(msg):
    print(msg, file=sys.stderr)


def run_diag(tsdr_file: str, out_dir: str, alpha: float, pc_stable: bool) -> Any:
    cmd = [DOCKER_DIAG, tsdr_file, "--citest-alpha", str(alpha), '--out-dir', out_dir]
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
        raise 'error run_diag'
    return proc


parser = argparse.ArgumentParser()
parser.add_argument("--out", help="out directory")
args = parser.parse_args([
    "--out", "/tmp/sockshop/combinations"
])

tsdr_files = [
    '/tmp/sockshop/argowf-chaos-9ztvw/carts-db_pod-cpu-hog_0.json/tsifter-2021-07-26-argowf-chaos-9ztvw.json',
]
for tsdr_file in tsdr_files:
    for pc_stable in [True, False]:
        for alpha in ALPHAS:
            run_diag(tsdr_file, args.out, alpha, pc_stable)

# %%
