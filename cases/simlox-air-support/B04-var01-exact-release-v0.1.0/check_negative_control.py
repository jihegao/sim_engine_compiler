"""Pin accepted B04 log and demonstrate its later allocation/launch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "B04-cross-midnight-turnround-v1.0.1/runs/b04-v101-turnround-20260930-01"
LOG_SHA = "ea2cd9cd124b499f69674a9bb8a70d44ec2ab9ffa0fa8b602f34b45f9e37163e"
OUT = HERE / "review/negative-control-accepted-parent.json"


def main():
    raw = (RUN / "model.log").read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != LOG_SHA:
        raise ValueError("accepted B04 log SHA differs")
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    gates = {
        "first_turnround_end": "Time: 24.5 <TEACH-AIR-01,0> turnround ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>",
        "second_allocation": "Time: 24.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>",
        "second_preparation_end": "Time: 25 <TEACH-AIR-01,0> preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>",
        "second_launch": "Time: 25 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2 : <TEACH-AIR-01,0>"
    }
    for label, wanted in gates.items():
        if lines.count(wanted) != 1:
            raise ValueError(f"accepted B04 control gate differs: {label}")
    result = {"schema": "simlox-b04-var01-parent-negative-control/v1", "accepted_log_sha256": LOG_SHA,
              "parent_gate_lines": gates, "child_h24_75_launch_gate_passed": False,
              "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode()
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists() and OUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
