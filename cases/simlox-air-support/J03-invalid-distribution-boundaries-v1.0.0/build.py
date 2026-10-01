"""Build two isolated negative distribution probes from accepted parents."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENTS = {
    "pfac-sum": (ROOT / "J03-var01-time-two-point-v1.0.0/seed-01-input.json",
                 "3f5e689c17ebb2696b30daec24b35042b2ee96a507604f1cf42523a7581cb917"),
    "cycle": (ROOT / "J03-var04-nested-time-v1.0.0/seed-01-input.json",
              "76cfad88b737a500d2393337043b4dd8be6a67b110f8e2391cbcd950a7086cc8"),
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table/instance")
    return matches[0]


def rows(item: dict) -> list[dict]:
    columns = [column["name"] for column in item["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in item["instances"][0]["rows"]]


def build() -> tuple[dict[str, bytes], bytes]:
    outputs: dict[str, bytes] = {}
    diffs: dict[str, dict] = {}
    for arm, (path, expected_sha) in PARENTS.items():
        raw = path.read_bytes()
        if sha(raw) != expected_sha:
            raise ValueError(f"accepted parent changed: {arm}")
        parent = json.loads(raw)
        doc = copy.deepcopy(parent)
        item = table(doc, "TimeDistributions")
        before = rows(item)
        if arm == "pfac-sum":
            if [(r["DISTID"], r["PFAC"], r["BASED"], r["PARAM1"]) for r in before] != [
                ("PREP-DET", 0.5, "<DETERM>", 0.25),
                ("PREP-DET", 0.5, "<DETERM>", 0.75),
            ]:
                raise ValueError("parent two-point support differs")
            item["instances"][0]["rows"][1][1] = 0.4
        else:
            if [(r["DISTID"], r["PFAC"], r["BASED"], r["PARAM1"]) for r in before] != [
                ("PREP-IN", 0.5, "<DETERM>", 0.25),
                ("PREP-IN", 0.5, "<DETERM>", 0.75),
                ("PREP-OUT", 1.0, "PREP-IN", 0.5),
            ]:
                raise ValueError("parent one-layer reference differs")
            item["instances"][0]["rows"][0][2] = "PREP-OUT"
            item["instances"][0]["rows"][0][3] = 0.5
        name = f"{arm}-input.json"
        outputs[name] = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        diffs[arm] = {
            "parent_case": "J03.var01@1.0.0" if arm == "pfac-sum" else "J03.var04@1.0.0",
            "parent_input_sha256": expected_sha,
            "input_sha256": sha(outputs[name]),
            "changed_table": "TimeDistributions",
            "before": before,
            "after": rows(item),
        }
        old = {t["name"]: t for t in parent["model"]["tables"]}
        new = {t["name"]: t for t in doc["model"]["tables"]}
        if [key for key in old if old[key] != new[key]] != ["TimeDistributions"]:
            raise ValueError("negative arm changed another table")
    manifest = {
        "schema": "simlox-j03-negative-distribution-probe-diff/v1",
        "publication_state": "diagnostic_only",
        "arms": diffs,
    }
    return outputs, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs, diff = build()
    outputs["probe-diff.json"] = diff
    for name, raw in outputs.items():
        path = HERE / name
        if args.check:
            if path.read_bytes() != raw:
                raise ValueError(f"probe source differs: {name}")
        else:
            path.write_bytes(raw)
    print(json.dumps({name: sha(raw) for name, raw in outputs.items()}))


if __name__ == "__main__":
    main()
