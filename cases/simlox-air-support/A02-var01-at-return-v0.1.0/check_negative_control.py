"""Show the accepted A02 parent fails the child second-launch h10 gate."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02/a02-bound-final-20260927-03")
PARENT_LOG_SHA = "5101ef9157f941627a2851774d884f9ec5abe92af894af0c177221749eca66ba"
OUTPUT = HERE / "review" / "negative-control-accepted-parent.json"

def main():
    path = PARENT_RUN / "model.log"
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha != PARENT_LOG_SHA:
        raise ValueError("accepted parent event log SHA differs")
    second = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2 : <TEACH-AIR-01,0>" in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            if not match:
                raise ValueError("second launch lacks time")
            second.append(float(match.group(1)))
    if second != [20.0] or second == [10.0]:
        raise ValueError(f"negative control does not discriminate: {second}")
    result = {"schema": "simlox-a02-var01-at-return-v010-negative-control/v1",
              "parent_log_sha256": actual_sha, "accepted_parent_second_start": second,
              "predeclared_child_second_start": [10.0], "child_gate_passed": False,
              "conclusion": "accepted parent fails child h10 second-launch gate as required",
              "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
