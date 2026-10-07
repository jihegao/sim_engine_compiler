"""Seal only publishable source; keep original native raw local and ignored."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = HERE.parent / "C05-var03-config-resource-v1.0.2"
RUN = ORIGINAL / "runs/c05-var03-v102-crew-ssh-20261007-01"
GATES = {
    "contract.json": "50c4f36e8756e1120db7c7e627cfb4713f387b5105fa116ed9d2affdce75ff8e",
    "review/independent-contract-go-2026-10-07.md": "aef173ea82dcacb2b581d7256a58a28390d6ad0c58e30851babd57ae4dd36cd5",
    "check_reclassification.py": "396d8bbee576ec6e264cd7b2bd250a16e740c42d16990fff26dea4c9733bc58e",
    "author-validation.json": "c118492d905a9ba46222f3da35f4c11908323f49b46e0c5f1792ab3e6d893584",
    "review/independent_replay.py": "fdabfbcf3477d2e0f7284cd9ae6e75bd03cd52b7ee344c60cc9d2a9fa30bcd09",
    "review/independent-verdict.json": "74fe434c7b5ca8b6e53e7e060ad5c9a67130b04aafe95a0e68edc72c2059e1fe",
    "review/independent-postrun-go-2026-10-07.md": "20be63300ca3925033ea958968c410b1027a8344dd865566fea086963e7f3e72",
}


def ident(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return os.path.relpath(path, HERE).replace("\\", "/")


def verify() -> tuple[dict, dict, dict, dict]:
    for name, sha in GATES.items():
        if ident(HERE / name)["sha256"] != sha:
            raise ValueError("exact GO source changed: " + name)
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-verdict.json")
    if (author["decision"] != "GO_BOUNDED" or author["checks"] != 6023 or
            author["passed"] != 6023 or author["failures"] or
            author["report_cells_compared"] != 5210):
        raise ValueError("author GO gate changed")
    if (independent["decision"] != "GO_BOUNDED_READONLY_COUNTEREXAMPLE" or
            independent["contract_sha256"] != GATES["contract.json"] or
            independent["report_cell_total"] != 5210 or
            independent["tamper_probes_rejected"] != 8 or
            independent["original_pair_decision"] != "NO_GO_FROZEN_PAIR" or
            independent["radio_arm"] != "not_started_not_tested"):
        raise ValueError("independent bounded GO gate changed")
    replay = subprocess.run([sys.executable, str(HERE / "check_reclassification.py")],
                            cwd=HERE, capture_output=True, check=True)
    if replay.stdout != (HERE / "author-validation.json").read_bytes():
        raise ValueError("author replay is no longer deterministic")
    if subprocess.run([sys.executable, str(HERE / "self_check.py")], cwd=HERE,
                      capture_output=True, check=True).stdout.strip() != b"self-check PASS: 9 in-memory negative probes":
        raise ValueError("negative self-check changed")
    original_manifest = read(ORIGINAL / "prelaunch-manifest.json")
    contract = read(HERE / "contract.json")
    for name, record in contract["pins"].items():
        path = ROOT / record["path"]
        if ident(path) != {key: record[key] for key in ("bytes", "sha256")}:
            raise ValueError("direct retrospective pin changed: " + name)
    closure = read(RUN / "closure.json")
    failure = read(RUN / "failure-seal.json")
    if (len(original_manifest["source_files"]) != 77 or
            len(closure["raw"]) != 13 or len(failure["files"]) != 15 or
            closure["error"] != "check_behavior rejected native result" or
            (ORIGINAL / "runs/c05-var03-v102-radio-ssh-20261007-01").exists()):
        raise ValueError("old failure/radio boundary changed")
    for item in original_manifest["source_files"]:
        if ident(Path(item["path"])) != {k: item[k] for k in ("bytes", "sha256")}:
            raise ValueError("77-pin original source changed: " + item["key"])
        if (closure["source_hashes_before"].get(item["key"]) != item["sha256"] or
                closure["source_hashes_after"].get(item["key"]) != item["sha256"]):
            raise ValueError("old before/after source changed: " + item["key"])
    for name, pin in closure["raw"].items():
        if ident(RUN / name) != pin:
            raise ValueError("crew raw changed: " + name)
    for name, pin in failure["files"].items():
        if ident(RUN / name) != pin:
            raise ValueError("failure seal changed: " + name)
    return original_manifest, closure, failure, independent


def build() -> dict:
    manifest, closure, failure, independent = verify()
    def include(path: Path) -> bool:
        return (path.is_file() and path.name != "evidence-index.json" and
                "__pycache__" not in path.parts and path.suffix != ".pyc" and
                "runs" not in path.parts and
                not path.name.startswith(("independent-staged-", "independent-remote-",
                                          "independent-publication-")))
    local = {rel(p): ident(p) for p in sorted(HERE.rglob("*")) if include(p)}
    historical = {}
    historical_raw = {}
    installed = {}
    for item in manifest["source_files"]:
        path = Path(item["path"])
        record = {"bytes": item["bytes"], "sha256": item["sha256"]}
        if path.is_relative_to(HERE.parent):
            if "runs" in path.parts:
                historical_raw[rel(path)] = record
            else:
                historical[rel(path)] = record
        else:
            installed[item["key"]] = {"path": str(path), **record}
    for item in read(HERE / "contract.json")["pins"].values():
        path = ROOT / item["path"]
        if path.is_relative_to(HERE.parent) and "runs" not in path.parts:
            historical[rel(path)] = {"bytes": item["bytes"], "sha256": item["sha256"]}
    original_contract = read(ORIGINAL / "contract.json")
    accepted_source_count = 0
    for accepted_source in original_contract["accepted_source_pins"].values():
        for relative, pair in accepted_source["files"].items():
            path = HERE.parent / accepted_source["package"] / relative
            if ident(path) != pair["local"]:
                raise ValueError("accepted local source changed: " + str(path))
            blob = subprocess.run(["git", "show", original_contract["base_commit"] + ":" +
                                   path.relative_to(ROOT).as_posix()], cwd=ROOT,
                                  capture_output=True, check=True).stdout
            if {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} != pair["published_git"]:
                raise ValueError("accepted published Git source changed: " + str(path))
            accepted_source_count += 1
    if accepted_source_count != 23:
        raise ValueError("accepted source count changed")
    accepted = {}
    total = 0
    for key, record in original_contract["accepted_native_runs"].items():
        folder = Path(record["path"])
        old = read(folder / "closure.json")
        if (ident(folder / "closure.json") != record["closure"] or
                ident(folder / "invocation.json") != record["invocation"] or
                old["raw"] != record["raw"]):
            raise ValueError("accepted raw header changed: " + key)
        for name, pin in old["raw"].items():
            if ident(folder / name) != pin:
                raise ValueError("accepted raw changed: " + key + "/" + name)
        accepted[key] = {"run_path": rel(folder), "closure": record["closure"],
                         "invocation": record["invocation"], "raw": record["raw"]}
        total += len(old["raw"])
    if total != 48:
        raise ValueError("accepted raw count changed")
    return {
        "schema": "c05-var03-counterexample-v010-evidence-index/v1",
        "case_id": "C05", "variant_id": "C05.var03", "version": "0.1.0",
        "classification": "retrospective_single_arm_counterexample",
        "publication_state": "pending", "new_native_runs": 0,
        "source_files": local,
        "historical_source_files": historical,
        "historical_raw_references": historical_raw,
        "installed_runtime_references": installed,
        "accepted_raw_runs": accepted, "accepted_raw_count": total,
        "failed_crew_run": {"run_path": rel(RUN),
                            "closure": ident(RUN / "closure.json"),
                            "invocation": ident(RUN / "invocation.json"),
                            "failure_seal": ident(RUN / "failure-seal.json"),
                            "raw": closure["raw"], "failure_files": failure["files"]},
        "author_validation": {"path": "author-validation.json", **ident(HERE / "author-validation.json")},
        "independent_verdict": {"path": "review/independent-verdict.json",
                                 **ident(HERE / "review/independent-verdict.json")},
        "author_checks": 6023, "independent_report_cells": independent["report_cell_total"],
        "original_pair_decision": "NO_GO_FROZEN_PAIR", "radio_arm": "not_started_not_tested",
        "scope": "one sealed crew-arm source-bound CLI counterexample; no new native calculation",
        "limits": "No accepted positive pair, radio behavior, general inheritance rule, GUI claim or serial item-to-aircraft continuity claim",
        "raw_location_policy": "local ignored raw; never publish raw under source_files",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    data = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.write:
        (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(result["source_files"]),
                      "historical_source_files": len(result["historical_source_files"]),
                      "historical_raw_references": len(result["historical_raw_references"]),
                      "accepted_raw": result["accepted_raw_count"],
                      "crew_raw": len(result["failed_crew_run"]["raw"]),
                      "index_sha256": hashlib.sha256(data).hexdigest()}))
