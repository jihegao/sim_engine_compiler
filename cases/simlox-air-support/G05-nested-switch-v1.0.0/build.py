"""Wrap the accepted G05 B/A passive switch in a series root with nonfailing C."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G05-passive-switchover-v1.0.0" / "half-input.json"
PARENT_SHA256 = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
TEMPLATE = ROOT / "G04-nested-series-parallel-v1.0.0" / "and-input.json"
TEMPLATE_SHA256 = "658cdfcc374a13754c0980888137dd05bb0b94c4dfad5386bab5292fc414dd15"
SOURCE = HERE / "nested-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(document: dict, name: str) -> list:
    return table(document, name)["instances"][0]["rows"]


def build() -> dict:
    parent_raw = PARENT.read_bytes()
    template_raw = TEMPLATE.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    assert sha(template_raw) == TEMPLATE_SHA256
    document = copy.deepcopy(json.loads(parent_raw))
    template = json.loads(template_raw)
    assert rows(document, "ProblemDescription") == [["G05 passive standby, TSWOV=0.5 h"]]
    rows(document, "ProblemDescription")[0][0] = "G05 nested series root, passive B/A switchover"
    operational = rows(document, "MaterielOperationalModes")
    assert operational[0] == ["TEACH-AIR-01", "G04-OPS", "G05-PASSIVE", None, 1.0, None]
    operational[0][2] = "G05-ROOT-SERIES"
    parallel = rows(document, "RBDParallel")
    assert parallel == [["G05-PASSIVE", "One operated of three with B/A/C priority", 1, 1, 0.5, "N", None]]
    parallel[0][1] = "One operated of B/A with B-first priority"
    structure = rows(document, "RBDParallelStructure")
    assert structure == [
        ["G05-PASSIVE", "POS-B", "G04-OPS", 1, 1, None],
        ["G05-PASSIVE", "POS-A", "G04-OPS", 1, 2, None],
        ["G05-PASSIVE", "POS-C", "G04-OPS", 1, 3, None],
    ]
    structure.pop()
    series = copy.deepcopy(table(template, "RBDSeries"))
    series["instances"][0]["rows"] = [["G05-ROOT-SERIES", "Passive B/A AND nonfailing C", None]]
    series_structure = copy.deepcopy(table(template, "RBDSeriesStructure"))
    series_structure["instances"][0]["rows"] = [
        ["G05-ROOT-SERIES", "G05-PASSIVE", None, 1, None],
        ["G05-ROOT-SERIES", "POS-C", "G04-OPS", 1, None],
    ]
    document["model"]["tables"].extend([series, series_structure])
    assert len({item["name"] for item in document["model"]["tables"]}) == len(document["model"]["tables"])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if SOURCE.exists():
            raise FileExistsError(SOURCE)
        SOURCE.write_bytes(data)
    elif SOURCE.read_bytes() != data:
        raise ValueError("frozen nested input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA256, "template_sha256": TEMPLATE_SHA256,
                      "source_sha256": sha(data), "bytes": len(data)}))


if __name__ == "__main__":
    main()
