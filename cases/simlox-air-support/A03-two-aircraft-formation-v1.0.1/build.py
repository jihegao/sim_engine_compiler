"""Build A03 1.0.1 by changing only the frozen 1.0.0 description."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "A03-two-aircraft-formation" / "native-input.json"
PREVIOUS_SHA256 = "51e3f99ecf86e05e35dce2b2c9e062b483a2c0f3dd64625761bc64c45900cce6"
A02 = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
A02_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OLD_DESCRIPTION = "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"
NEW_DESCRIPTION = "A03 two-aircraft, one-wave teaching case; no J35/F35 equivalence"
EXPECTED_REVISION_TABLES = ["ProblemDescription"]
EXPECTED_PARENT_TABLES = ["MissionType", "OperationProfile", "ProblemDescription", "SystemDeployment"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(document: dict, name: str) -> list[dict]:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    columns = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in found[0]["instances"][0]["rows"]]


def changed_tables(before: dict, after: dict) -> dict:
    before_names = [item["name"] for item in before["model"]["tables"]]
    after_names = [item["name"] for item in after["model"]["tables"]]
    if before_names != after_names:
        raise ValueError("native table layout changed")
    return {name: {"before_rows": rows(before, name), "after_rows": rows(after, name)}
            for name in before_names if rows(before, name) != rows(after, name)}


def build() -> bytes:
    if sha256(PREVIOUS) != PREVIOUS_SHA256 or sha256(A02) != A02_SHA256:
        raise ValueError("frozen A03 1.0.0 or A02 input changed")
    previous_raw = PREVIOUS.read_bytes()
    old = OLD_DESCRIPTION.encode("utf-8")
    if previous_raw.count(old) != 1:
        raise ValueError("frozen A03 description is not unique")
    previous = json.loads(previous_raw)
    if rows(previous, "ProblemDescription") != [{"PDESC": OLD_DESCRIPTION}]:
        raise ValueError("unexpected frozen A03 description row")
    candidate_raw = previous_raw.replace(old, NEW_DESCRIPTION.encode("utf-8"), 1)
    candidate = json.loads(candidate_raw)
    a02 = json.loads(A02.read_bytes())
    if sorted(changed_tables(previous, candidate)) != EXPECTED_REVISION_TABLES:
        raise ValueError("A03 revision changed more than ProblemDescription")
    if sorted(changed_tables(a02, candidate)) != EXPECTED_PARENT_TABLES:
        raise ValueError("A02 to A03 1.0.1 changed unexpected tables")
    if rows(candidate, "ProblemDescription") != [{"PDESC": NEW_DESCRIPTION}]:
        raise ValueError("candidate description mismatch")
    return candidate_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = build()
    output = HERE / "native-input.json"
    if args.check:
        if not output.is_file() or output.read_bytes() != raw:
            raise ValueError("A03 1.0.1 checked input differs from frozen builder")
    else:
        output.write_bytes(raw)
    print(json.dumps({"previous_sha256": PREVIOUS_SHA256, "a02_sha256": A02_SHA256,
                      "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "revision_tables": EXPECTED_REVISION_TABLES,
                      "a02_parent_tables": EXPECTED_PARENT_TABLES}))


if __name__ == "__main__":
    main()
