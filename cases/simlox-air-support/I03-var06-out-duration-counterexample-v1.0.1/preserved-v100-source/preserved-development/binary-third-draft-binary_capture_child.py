"""Harmless process emitting fixed binary streams for captured_process.ps1 tests."""
from __future__ import annotations

import argparse
import os
import time

STDOUT = b"OUT\xff\x00\r\nA\x80\n"
STDERR = b"ERR\xfe\x00\r\nB\x81\n"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit", type=int, choices=(0, 7), required=True)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()
    time.sleep(args.sleep)
    os.write(1, STDOUT)
    os.write(2, STDERR)
    raise SystemExit(args.exit)
