"""Build the package-relative source and accepted-raw evidence map, read-only by default."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from check_reclassification import HERE, CONTRACT_SHA, digest, load, run
from self_check import main as self_check

INDEPENDENT = {
    "review/independent_replay.py": "6e2c4b7271a94d3523b79c35e8ce378672310b601e65d9f64b0f7537d15cf82d",
    "review/independent-verdict.json": "d7f6f10273be5cc75eb271018fc5aae9253a2966d97fcd1c0cad663a63ef3eea",
    "review/independent-postrun-review-2026-10-07.md": "297b06c1e18ce14eb471432ec10453a93c53075c8619e8a73381f0240c8bfee8",
    "review/independent-contract-go-2026-10-07.md": "f7a3b4c86412418d9107aed91a7fc2ec0e33b7baa145bd7d6fda648b70b5641a",
}
AUTHOR_VERDICT_SHA = "62728d93de561fab3456cb7ae1225b2d9de9d24b90609087b0e1b8ff9cb7da35"


def rel(path: Path) -> str:
    return Path(os.path.relpath(path, HERE)).as_posix()


def reference(path: Path) -> dict:
    assert path.is_file(), path
    return {"path": rel(path), **digest(path.read_bytes())}


def build() -> dict:
    contract = load(HERE / "contract.json")
    assert digest((HERE / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA
    assert run()["decision"] == "GO_BOUNDED"
    assert self_check()["decision"] == "PASS"
    author = HERE / "author-validation.json"
    assert digest(author.read_bytes())["sha256"] == AUTHOR_VERDICT_SHA
    author_data = load(author)
    assert author_data["decision"] == "GO_BOUNDED" and author_data["checks"] == 16212 and author_data["report_cells"] == 15630
    for name, sha in INDEPENDENT.items():
        assert digest((HERE / name).read_bytes())["sha256"] == sha, name
    independent = load(HERE / "review/independent-verdict.json")
    assert independent["decision"] == "GO_BOUNDED" and independent["checks"] == 15892
    assert independent["report_cells"] == {"local": 5210, "remote": 5210, "remote-disabled": 5210}

    source_paths: set[Path] = set()
    for package in (HERE, HERE.parent / "C09-var03-consecutive-reuse-v0.1.0"):
        for path in package.rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(package).parts
            if "runs" in parts or "__pycache__" in parts or path.suffix == ".pyc":
                continue
            if path.name == "evidence-index.json" or path.name.startswith(("independent-staged", "independent-remote", "independent-publication")):
                continue
            source_paths.add(path.resolve())

    parent = contract["accepted_C09_var04"]
    source_paths.add((HERE / parent["evidence_index"]["path"]).resolve())
    for record in parent["source_files"].values():
        source_paths.add((HERE / record["path"]).resolve())
    source_paths.add((HERE / contract["catalog"]["source"]["path"]).resolve())
    for item in contract["prerequisites"].values():
        for record in item["source_files"].values():
            source_paths.add((HERE / record["path"]).resolve())
    source = [reference(path) for path in sorted(source_paths, key=lambda p: rel(p))]
    assert len({item["path"] for item in source}) == len(source)

    raw = []
    for arm, data in parent["accepted_runs"].items():
        raw.append({"arm": arm, "run_id": data["run_id"], "closure": reference((HERE / data["path"] / "closure.json").resolve()),
                    "invocation": reference((HERE / data["path"] / "invocation.json").resolve()),
                    "files": [reference((HERE / data["path"] / name).resolve()) for name in sorted(data["raw"])]})
    for prerequisite, data in contract["prerequisites"].items():
        item = data["accepted_run"]
        raw.append({"arm": prerequisite, "run_id": item["run_id"], "closure": reference((HERE / item["path"] / "closure.json").resolve()),
                    "invocation": reference((HERE / item["path"] / "invocation.json").resolve()),
                    "files": [reference((HERE / item["path"] / name).resolve()) for name in sorted(item["raw"])]})
    assert len(raw) == 6 and sum(len(item["files"]) for item in raw) == 71
    # Every reference is rechecked against the frozen contract, not merely hashed afresh.
    for arm, data in parent["accepted_runs"].items():
        record = next(item for item in raw if item["arm"] == arm)
        assert record["closure"]["sha256"] == data["closure"]["sha256"]
        assert record["invocation"]["sha256"] == data["invocation"]["sha256"]
        assert {Path(item["path"]).name: item["sha256"] for item in record["files"]} == {name: value["sha256"] for name, value in data["raw"].items()}
    for group, data in contract["prerequisites"].items():
        item = data["accepted_run"]
        record = next(entry for entry in raw if entry["arm"] == group)
        assert record["closure"]["sha256"] == item["closure"]["sha256"]
        assert record["invocation"]["sha256"] == item["invocation"]["sha256"]
        assert {Path(x["path"]).name: x["sha256"] for x in record["files"]} == {name: value["sha256"] for name, value in item["raw"].items()}
    return {"schema": "c09-var03-consecutive-reuse-v011-evidence-index/v1",
            "case_id": "C09", "variant_id": "C09.var03", "version": "0.1.1",
            "classification": "retrospective_source_bound_consecutive_reuse",
            "publication_state": "content_GO_publication_pending", "new_native_runs": 0,
            "source": source, "source_count": len(source),
            "accepted_raw_runs": raw, "accepted_raw_count": 71,
            "contract_sha256": CONTRACT_SHA,
            "author_validation_sha256": AUTHOR_VERDICT_SHA,
            "author_checks": 16212,
            "independent_verdict_sha256": INDEPENDENT["review/independent-verdict.json"],
            "independent_checks": 15892, "report_cells": 15630,
            "excluded_v010_decision": "NO_GO_CONTRACT",
            "scope": "one borrowed quantity released and rebooked at printed h9.28243; no persistent person ID",
            "raw_location_policy": "original accepted runs remain local and are never staged"}


if __name__ == "__main__":
    result = build()
    output = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if "--write" in sys.argv:
        (HERE / "evidence-index.json").write_bytes(output)
    else:
        sys.stdout.buffer.write(output)
