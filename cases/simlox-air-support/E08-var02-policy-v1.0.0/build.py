"""Build the E08 LSRUL EXTENDED/ADJACENT contrast from accepted IMMEDIATE."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2" / "on-input.json"
PARENT_SHA = "630d7600e7ff77ddb057f05af0852b4f41ed6335718570f9fcf5eddd9f51c474"
POLICIES = ("extended", "adjacent")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(policy):
    assert policy in POLICIES
    assert sha(PARENT) == PARENT_SHA, "accepted E08 parent changed"
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    lateral = tables["LateralSupport"]
    names = [c["name"] for c in lateral["columns"]]
    lateral["instances"][0]["rows"][0][names.index("LSRUL")] = policy.upper()
    description = tables["ProblemDescription"]
    names = [c["name"] for c in description["columns"]]
    description["instances"][0]["rows"][0][names.index("PDESC")] = (
        f"E08 {policy.upper()} lateral policy; stocked peer and stocked ordinary depot"
    )
    return doc


if __name__ == "__main__":
    for policy in POLICIES:
        raw = (json.dumps(build(policy), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{policy}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {policy} source differs"
        else:
            path.write_bytes(raw)
        print(policy, sha(path), len(raw))
