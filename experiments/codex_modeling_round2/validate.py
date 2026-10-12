#!/usr/bin/env python3
"""Public execution-only entry: never reads round-two tasks or private scoring."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from experiments.codex_modeling_pilot.runner import main

if __name__ == "__main__":
    # Preserve pilot's CLI but unconditionally choose the oracle-free command.
    raise SystemExit(main(["validate", *sys.argv[1:]]))
