"""Seal accepted B01 event log and show its h7 preparation is not the child gate."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06")
LOG_SHA = "140dab2eb1031c8b6e6cff68f82b6d8004236ec71029d27d92daa1334250ad5f"
OUT = HERE / "review/negative-control-accepted-parent.json"


def main():
    raw = (RUN / "model.log").read_bytes()
    if hashlib.sha256(raw).hexdigest() != LOG_SHA:
        raise ValueError("accepted B01 log SHA differs")
    lines = raw.decode("utf-8-sig").splitlines()
    starts = [x for x in lines if "<TEACH-AIR-01,0> preparation started, mission:" in x]
    ends = [x for x in lines if "<TEACH-AIR-01,0> preparation ended, mission:" in x]
    if len(starts) != 1 or not starts[0].startswith("Time: 7 ") or len(ends) != 1 or not ends[0].startswith("Time: 7.5 "):
        raise ValueError("accepted B01 preparation timing differs")
    result = {"schema": "simlox-b01-var02-parent-negative-control/v1", "accepted_log_sha256": LOG_SHA,
              "parent_preparation_start": starts[0], "parent_preparation_end": ends[0],
              "child_h7_5_start_gate_passed": False, "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode()
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists() and OUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
