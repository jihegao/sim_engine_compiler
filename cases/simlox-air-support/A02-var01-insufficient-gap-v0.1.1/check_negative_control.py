"""Show accepted parent and published sibling fail the timeout child gate."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_LOG = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02/a02-bound-final-20260927-03/model.log")
SIBLING_LOG = HERE.parent / "A02-var01-at-return-v0.1.1/runs/a02-var01-at-return-v011-ssh-20261006-01/model.log"
PARENT_SHA = "5101ef9157f941627a2851774d884f9ec5abe92af894af0c177221749eca66ba"
SIBLING_SHA = "e3c2e0e4ace201660d6f43cde71ea04d1abb84c7bfdb61273884620d20116858"
OUTPUT = HERE / "review/negative-control-parent-and-sibling.json"


def inspect(path, expected_sha):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError(f"accepted log SHA differs: {path}")
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    return {"sha256": expected_sha,
            "second_launch_lines": [line for line in lines if tag + " mission starting" in line],
            "second_cancel_lines": [line for line in lines if tag in line and ("mission cancelled" in line.lower() or "mission canceled" in line.lower() or "mission timed out" in line.lower())]}


def main():
    parent = inspect(PARENT_LOG, PARENT_SHA)
    sibling = inspect(SIBLING_LOG, SIBLING_SHA)
    if len(parent["second_launch_lines"]) != 1 or not parent["second_launch_lines"][0].startswith("Time: 20 "):
        raise ValueError("accepted A02 second launch changed")
    if len(sibling["second_launch_lines"]) != 1 or not sibling["second_launch_lines"][0].startswith("Time: 10 "):
        raise ValueError("published at-return second launch changed")
    if parent["second_cancel_lines"] or sibling["second_cancel_lines"]:
        raise ValueError("negative control has second cancellation")
    result = {"schema": "simlox-a02-var01-insufficient-gap-v011-negative-control/v1",
              "accepted_parent": parent, "published_at_return_sibling": sibling,
              "child_gate_passed": False, "native_process_started": False,
              "conclusion": "both accepted controls launch mission 1 and fail the proposed no-launch cancellation gate"}
    data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUTPUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
