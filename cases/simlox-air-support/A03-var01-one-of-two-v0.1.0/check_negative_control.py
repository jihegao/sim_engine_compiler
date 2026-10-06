"""Pin the accepted two-aircraft A03 launch as a negative control."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(r"C:\Users\user\Documents\Codex\2026-09-28\simlox-issue18-ssh-current\cases\simlox-air-support\A03-two-aircraft-formation-v1.0.1\runs\a03-v101-ssh-gui-20260929-01")
LOG_SHA = "5a88edd86e6fe3dfab96cb9fee12c7d327e9fe56b202be9c4f58918b06476809"
OUT = HERE / "review/negative-control-accepted-parent.json"


def main():
    raw = (RUN / "model.log").read_bytes()
    if hashlib.sha256(raw).hexdigest() != LOG_SHA:
        raise ValueError("accepted A03 log SHA differs")
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    gates = {
        "notice": "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        "requested_two": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission activated, systems requested: 2",
        "aircraft_zero": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
        "aircraft_one": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,1>",
        "two_aircraft_launch": "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        "two_aircraft_completion": "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"
    }
    for label, wanted in gates.items():
        if lines.count(wanted) != 1:
            raise ValueError(f"accepted A03 control gate differs: {label}")
    result = {"schema": "simlox-a03-var01-parent-negative-control/v1",
              "accepted_log_sha256": LOG_SHA, "parent_gate_lines": gates,
              "child_below_mnos_gate_passed": False, "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode()
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists() and OUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
