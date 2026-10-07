"""Harmless process emitting fixed binary streams for captured_process.ps1 tests."""
from __future__ import annotations

import argparse
import os
import time

STDOUT = b"OUT\xff\x00\r\nA\x80\n"
STDERR = b"ERR\xfe\x00\r\nB\x81\n"


def write_all(fd: int, payload: bytes) -> None:
    cursor = 0
    while cursor < len(payload):
        cursor += os.write(fd, payload[cursor:])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit", type=int, choices=(0, 7), required=True)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    assert 1 <= args.repeat <= 131072
    time.sleep(args.sleep)
    write_all(1, STDOUT * args.repeat)
    write_all(2, STDERR * args.repeat)
    raise SystemExit(args.exit)
