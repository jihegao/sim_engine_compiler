"""Build one B04 turnround breakdown contrast from the accepted v1.0.1 input."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-cross-midnight-turnround-v1.0.1" / "turnround-input.json"
PARENT_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted B04 parent bytes differ")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    tasks = tables["Tasks"]["instances"][0]["rows"]
    breakdown = tables["TaskBreakDown"]["instances"][0]["rows"]
    turnround = tables["MissionTurnround"]["instances"][0]["rows"]
    if len(tasks) != 1 or len(breakdown) != 2 or len(turnround) != 1:
        raise ValueError("accepted B04 task topology differs")
    if tasks[0][0] != "PREP-FIXED":
        raise ValueError("accepted preparation task differs")
    if breakdown != [
        ["PREP-FIXED", 1, "INSPECT", 1 / 6, None, None],
        ["PREP-FIXED", 2, "SERVICE", 1 / 3, None, None],
    ]:
        raise ValueError("accepted preparation breakdown differs")
    if turnround[0] != ["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 1.0, None, None, None]:
        raise ValueError("accepted scalar turnround differs")
    tasks.append(["TURN-STEPS", "Serial 10+20-minute post-mission turnround", None, None, None])
    breakdown.extend(
        [["TURN-STEPS", seq, subtask, duration, None, None]
         for seq, subtask, duration in ((1, "INSPECT", 1 / 6), (2, "SERVICE", 1 / 3))]
    )
    turnround[0][4] = "TURN-STEPS"
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(output)
    elif OUTPUT.read_bytes() != output:
        raise ValueError("frozen child differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "child_sha256": hashlib.sha256(output).hexdigest(),
                      "bytes": len(output)}))


if __name__ == "__main__":
    main()
