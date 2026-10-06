"""Pin accepted one-of-two cancellation as the no-launch negative control."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "A03-var01-one-of-two-v0.1.0/runs/a03-var01-one-of-two-v010-ssh-20261006-01"
LOG_SHA = "bd3caad8ea86da0a7402ad6beeac3cc548c3e86d2b66d5a4b058417f86ded506"
OUT = HERE / "review/negative-control-accepted-parent.json"


def main():
    raw = (RUN / "model.log").read_bytes()
    if hashlib.sha256(raw).hexdigest() != LOG_SHA:
        raise ValueError("accepted one-of-two log SHA differs")
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    gates = {
        "notice": "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        "requested_two": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission activated, systems requested: 2",
        "one_allocation": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
        "waiting": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission waiting:  timeout at 8.33333",
        "cancellation": "Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled: ",
        "physical_release": "Time: 8.33333 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, "
    }
    for label, wanted in gates.items():
        if lines.count(wanted) != 1:
            raise ValueError(f"accepted one-of-two gate differs: {label}")
    if any(" mission starting," in line or " mission success:" in line for line in lines):
        raise ValueError("accepted no-launch control differs")
    result = {"schema": "simlox-a03-var01-min-one-parent-negative-control/v1",
              "accepted_log_sha256": LOG_SHA, "parent_gate_lines": gates,
              "child_on_time_h8_launch_gate_passed": False, "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode()
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists() and OUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
