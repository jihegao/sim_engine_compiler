"""Build C06.var03 evidence index after independent postrun GO; never invoke native."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from check_roundtrip import parse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = HERE.parent
CONTRACT_SHA = "48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384"
MANIFEST_SHA = "96e62ff1d1bd532df45bca301b5d3635fad9a636d8a6de0c91b7dd01d58648e7"
APPROVAL_SHA = "500c4e8e37aca3b279365eb54aebabf1c812aebe1d7e04dcfeb3967f8d512cc5"
CONTRACT_REVIEW_SHA = "e812a38a3bdc330ac4b0ebf355a0b976303c11586df8f99cfbf210d9601830fb"
CLOSURE_SHA = {
    "factor1": "c81a9187f4eaa81527569c23d5986244a755c3c36c785765daa48827a71de360",
    "factor3": "9c04671966c7226f86cfe4f22efaba7d9e8dfa1a1d44c235ab33851265564a71",
}
RUN_IDS = {arm: f"c06-var03-v101-{arm}-ssh-20261007-01" for arm in CLOSURE_SHA}
INDEPENDENT_SCRIPT_SHA = "32f5e292c7fc058c4155bc1cbab13e4aec40523629ea405c644518d62de53bfb"
INDEPENDENT_VERDICT_SHA = "465a5f2242137fc434fb2ae1ca8be3b40e955b85efc8af513f900cc7793965c1"
INDEPENDENT_MEMO_SHA = "8dbb1c65c1204d2caf7d3afa40f65bd2f4d4410b68cb435fd7f6888e0607d197"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_pin(path: Path) -> dict:
    data = subprocess.run(["git", "show", "HEAD:" + path.relative_to(REPO).as_posix()],
                          cwd=REPO, capture_output=True, check=True).stdout
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def require(path: Path, digest: str) -> None:
    if len(digest) != 64 or pin(path)["sha256"] != digest:
        raise ValueError(f"exact source pin differs: {path}")


def accepted_source(record: dict, expected_count: int) -> dict:
    package = ROOT / record["package"]
    files = record["source_files"]
    tracked = subprocess.run(["git", "ls-files", "--", package.relative_to(REPO).as_posix()],
                             cwd=REPO, capture_output=True, check=True, text=True).stdout.splitlines()
    if len(files) != expected_count or {str((REPO / name).relative_to(package)).replace("\\", "/") for name in tracked} != set(files):
        raise ValueError("accepted published source set differs: " + package.name)
    for name, item in files.items():
        path = package / name
        if pin(path) != item["local_disk"] or git_pin(path) != item["published_git"]:
            raise ValueError("accepted published source byte pin differs: " + str(path))
    return record


def sealed_old_run(record: dict, count: int) -> dict:
    run = Path(record["path"])
    if pin(run / "closure.json") != record["closure"] or pin(run / "invocation.json") != record["invocation"]:
        raise ValueError("accepted closure/invocation seal differs: " + run.name)
    closure = read(run / "closure.json")
    if closure["raw"] != record["raw"] or len(record["raw"]) != count:
        raise ValueError("accepted raw map differs: " + run.name)
    if closure["invocation_sha256"].lower() != record["invocation"]["sha256"]:
        raise ValueError("accepted invocation link differs: " + run.name)
    for name, item in record["raw"].items():
        if pin(run / name) != item:
            raise ValueError("accepted raw byte seal differs: " + run.name + "/" + name)
    return record


def sealed_child(arm: str, manifest: dict) -> dict:
    run = HERE / "runs" / RUN_IDS[arm]
    require(run / "closure.json", CLOSURE_SHA[arm])
    closure = read(run / "closure.json")
    invocation = read(run / "invocation.json")
    if (closure["run_id"] != RUN_IDS[arm] or invocation["run_id"] != RUN_IDS[arm]
            or invocation["arm"] != arm or closure["error"] != "" or len(closure["raw"]) != 13
            or closure["invocation_sha256"].lower() != pin(run / "invocation.json")["sha256"]):
        raise ValueError("child run identity/closure differs: " + arm)
    expected_sources = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    if (closure["source_hashes_before"] != expected_sources
            or closure["source_hashes_after"] != expected_sources
            or invocation["source_hashes_before"] != expected_sources):
        raise ValueError("child source before/after map differs: " + arm)
    if (invocation["manifest_sha256"] != MANIFEST_SHA or invocation["approval_sha256"] != APPROVAL_SHA
            or closure["manifest_sha256"] != MANIFEST_SHA or closure["approval_sha256"] != APPROVAL_SHA):
        raise ValueError("child manifest/approval binding differs: " + arm)
    for name, expected in closure["raw"].items():
        if pin(run / name) != expected:
            raise ValueError("child raw SHA/size seal differs: " + arm + "/" + name)
    steps = read(run / "steps.json")
    if ([x["name"] for x in steps] != ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
            or any(x["status"] != "completed" or x["exit_code"] != 0 or x["gui_preserved"] is not True for x in steps)):
        raise ValueError("child six-step guarded closure differs: " + arm)
    native_steps = [x for x in steps if x["name"] in ("import", "export", "calc", "jsonreport")]
    if any(x["child_session_id"] != 0 or not isinstance(x["child_pid"], int) or x["child_pid"] <= 0 for x in native_steps):
        raise ValueError("child native session differs: " + arm)
    if len({x["child_pid"] for x in native_steps}) != 4:
        raise ValueError("native child PIDs are not distinct: " + arm)
    author = read(run / "author-validation.json")
    if author["decision"] != "GO_BOUNDED" or author["passed"] != 5703 or author["checks"] != 5703 or author["failures"]:
        raise ValueError("author physical/report gate differs: " + arm)
    roundtrip = read(run / "roundtrip-validation.json")
    if roundtrip["passed"] is not True or roundtrip["authored_row_tables"] != 20:
        raise ValueError("authored roundtrip differs: " + arm)
    report = parse(run / "report-raw.json")
    selected = {t["name"]: t for t in report["report"]["tables"]}
    shape = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11), "SystemResults": (72, 40),
             "StockTotalResults": (72, 16), "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
    if set(selected) != set(shape) or sum(n*m for n, m in shape.values()) != 5210:
        raise ValueError("report table shape differs: " + arm)
    for name, (rows, cols) in shape.items():
        data = selected[name]["instances"][0]["rows"]
        if len(data) != rows or any(len(row) != cols for row in data):
            raise ValueError("report row/width differs: " + arm + "/" + name)
    return {"run_id": RUN_IDS[arm], "closure": pin(run / "closure.json"), "invocation": pin(run / "invocation.json"),
            "raw": closure["raw"], "raw_count": 13, "author_checks": 5703, "report_cells": 5210}


def include(path: Path) -> bool:
    rel = path.relative_to(HERE)
    return (path.is_file() and "runs" not in rel.parts and "__pycache__" not in rel.parts
            and path.suffix != ".pyc" and path.name != "evidence-index.json"
            and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-")))


def build(pre_independent: bool = False) -> dict:
    require(HERE / "contract.json", CONTRACT_SHA)
    require(HERE / "prelaunch-manifest.json", MANIFEST_SHA)
    require(HERE / "review" / "independent-contract-go-2026-10-07.md", CONTRACT_REVIEW_SHA)
    require(HERE / "review" / "independent-prelaunch-go.json", APPROVAL_SHA)
    contract = read(HERE / "contract.json")
    manifest = read(HERE / "prelaunch-manifest.json")
    for entry in manifest["source_files"]:
        if pin(Path(entry["path"])) != {"bytes": entry["bytes"], "sha256": entry["sha256"]}:
            raise ValueError("prelaunch source inventory differs: " + entry["key"])
    diagnostic = contract["excluded_diagnostic"]
    if diagnostic["classification"] != "NO_GO_CONTRACT" or diagnostic["native_child_count"] != 0:
        raise ValueError("old contract exclusion differs")
    for key in ("frozen_contract", "independent_no_go_memo"):
        item = diagnostic[key]
        if pin(ROOT / item["path"]) != {"bytes": item["bytes"], "sha256": item["sha256"]}:
            raise ValueError("old contract diagnostic pin differs: " + key)
    c06 = accepted_source(contract["accepted_C06_parent"], 17)
    c03 = accepted_source(contract["accepted_C03_prerequisite"], 16)
    sealed_old_run(c06["run"], 12)
    sealed_old_run(c03["staffing_2_run"], 11)
    children = {arm: sealed_child(arm, manifest) for arm in CLOSURE_SHA}
    independent = None
    if not pre_independent:
        for name, digest in (("review/independent_replay.py", INDEPENDENT_SCRIPT_SHA),
                             ("review/independent-verdict.json", INDEPENDENT_VERDICT_SHA),
                             ("review/independent-postrun-review-2026-10-07.md", INDEPENDENT_MEMO_SHA)):
            require(HERE / name, digest)
        independent = read(HERE / "review" / "independent-verdict.json")
        if (independent.get("decision") != "GO_BOUNDED" or independent.get("checks") != 11774
                or independent.get("contract_sha256") != CONTRACT_SHA or independent.get("failures")):
            raise ValueError("independent postrun result is not GO")
    source = [{"path": path.relative_to(HERE).as_posix(), **pin(path)}
              for path in sorted(HERE.rglob("*")) if include(path)]
    return {"schema": "c06-var03-v101-evidence-index/v1", "case_id": "C06", "variant_id": "C06.var03",
            "version": "1.0.1", "publication_state": "not_published", "status": "pending_independent" if pre_independent else "bounded_native_evidence_ready_for_publication",
            "source": source, "prelaunch_manifest": {"path": "prelaunch-manifest.json", **pin(HERE / "prelaunch-manifest.json")},
            "prelaunch_approval": {"path": "review/independent-prelaunch-go.json", **pin(HERE / "review/independent-prelaunch-go.json")},
            "accepted_C06_parent": c06, "accepted_C03_prerequisite": c03, "excluded_diagnostic": diagnostic,
            "new_native_runs": children, "new_raw_count": 26, "accepted_raw_count": 23,
            "author_checks_per_arm": 5703, "report_cells_per_arm": 5210,
            "independent": independent,
            "scope": "Fixed two-aircraft, two-alternative-resource native CLI pair; factor1 40min and factor3 60min.",
            "limits": "No general alternative-selection law, stochastic result, GUI-only result, or different-task topology claim.",
            "raw_location_policy": "local_ignored_native_runs_not_committed"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-independent", action="store_true", help="read-only all available gates; never writes an index")
    parser.add_argument("--write", action="store_true", help="write only after exact independent GO pins are filled")
    args = parser.parse_args()
    if args.pre_independent and args.write:
        raise ValueError("pre-independent mode cannot write")
    result = build(pre_independent=args.pre_independent)
    if args.pre_independent:
        print(json.dumps({"status": result["status"], "source_count": len(result["source"]),
                          "new_raw_count": result["new_raw_count"], "accepted_raw_count": result["accepted_raw_count"]}))
        return
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(raw)
    elif not destination.exists() or destination.read_bytes() != raw:
        raise ValueError("index absent or stale; independent postrun GO and --write required")
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "source_count": len(result["source"])}))


if __name__ == "__main__":
    main()
