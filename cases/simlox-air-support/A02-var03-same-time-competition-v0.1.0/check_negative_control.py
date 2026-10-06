"""Show both accepted controls fail the two-at-h7 mission-creation gate."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02/a02-bound-final-20260927-03/model.log")
ANALOGUE = HERE.parent / "A02-var01-insufficient-gap-v0.1.1/runs/a02-var01-insufficient-gap-v011-ssh-20261006-01/model.log"
PARENT_SHA = "5101ef9157f941627a2851774d884f9ec5abe92af894af0c177221749eca66ba"
ANALOGUE_SHA = "ae99693f61618e10212b414855aee1995f3744b73f8a3960d8955ebbd5ab3514"
OUTPUT = HERE / "review/negative-control-accepted-parent-and-analogue.json"


def inspect(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted log SHA differs: {path}")
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    created = [line for line in lines if line.startswith("Time: 7 ") and " mission created:" in line]
    return {"sha256": expected, "created_at_h7": created,
            "two_at_h7_gate": len(created) == 2}


def main():
    parent = inspect(PARENT, PARENT_SHA)
    analogue = inspect(ANALOGUE, ANALOGUE_SHA)
    if len(parent["created_at_h7"]) != 1 or len(analogue["created_at_h7"]) != 1:
        raise ValueError("accepted controls' h7 creation changed")
    value = {"schema": "simlox-a02-var03-same-time-v010-negative-control/v1",
             "accepted_parent": parent, "accepted_insufficient_gap_analogue": analogue,
             "child_gate_passed": False, "native_process_started": False,
             "conclusion": "neither accepted control creates two distinct mission identities at h7"}
    data = (json.dumps(value, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUTPUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
