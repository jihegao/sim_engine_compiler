"""Build the C04.var02 source index only after independent postrun replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ACCEPTED = HERE.parent / "C04-deadline-cancellation-v1.0.0"
C03 = HERE.parent / "C03-shared-crew-formation-v1.0.2"
EXCLUDED = HERE.parent / "C04-var02-cutoff-boundary-v0.1.0"
CONTRACT_SHA = "0d71443048ec3499d0610e73e702409574c6e52df80047102b18cb12bd5069ee"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def included(path: Path) -> bool:
    return (
        path.is_file()
        and path.name != "evidence-index.json"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-"))
    )


def local_sources(package: Path, base: Path) -> list[dict]:
    return [
        {"path": path.relative_to(base).as_posix(), **pin(path)}
        for path in sorted(package.rglob("*"))
        if included(path)
    ]


def accepted_sources(contract) -> list[dict]:
    prefix = ACCEPTED.relative_to(REPO).as_posix()
    listed = subprocess.run(
        ["git", "ls-files", "--", prefix], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    expected = {item["path"]: item for item in contract["accepted_source"]["published_source_files"]}
    if len(listed) != len(expected) or len(expected) != 25:
        raise ValueError("accepted C04 published source set differs")
    for relative in listed:
        path = REPO / relative
        name = path.relative_to(ACCEPTED).as_posix()
        record = expected[name]
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative.replace(chr(92), '/')}"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        if pin(path) != record["local_disk"]:
            raise ValueError(f"accepted C04 local source differs: {name}")
        if {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} != record["published_git"]:
            raise ValueError(f"accepted C04 Git source differs: {name}")
        if path.read_bytes() != blob:
            raise ValueError(f"accepted C04 source byte divergence: {name}")
    return contract["accepted_source"]["published_source_files"]


def sealed_run(run: Path, expected: dict) -> dict:
    closure_path = run / "closure.json"
    if pin(closure_path) != expected["closure"]:
        raise ValueError(f"run closure differs: {run.name}")
    closure = load(closure_path)
    if closure["raw"] != expected["raw"] or len(closure["raw"]) != 11:
        raise ValueError(f"run raw map differs: {run.name}")
    if pin(run / "invocation.json") != expected["invocation"]:
        raise ValueError(f"run invocation differs: {run.name}")
    if closure["invocation_sha256"] != expected["invocation"]["sha256"]:
        raise ValueError(f"run invocation closure differs: {run.name}")
    for name, seal in closure["raw"].items():
        if pin(run / name) != seal:
            raise ValueError(f"raw file seal differs: {run.name}/{name}")
    return {"run_id": run.name, "local_run_dir": str(run),
            "closure": expected["closure"], "invocation": expected["invocation"], "raw": closure["raw"]}


def build():
    if pin(HERE / "contract.json")["sha256"] != CONTRACT_SHA:
        raise ValueError("corrected contract differs")
    contract = load(HERE / "contract.json")
    if pin(EXCLUDED / "contract.json")["sha256"] != "9f30694d4046b0d15cdfd72f89563e9f159980130d8055825bd3ce6893b3c555":
        raise ValueError("excluded v0.1.0 contract differs")
    if pin(EXCLUDED / "review/independent-contract-no-go-2026-10-07.md")["sha256"] != "ea388c2092743ccfa46030c40ffe8360b52e4eb3aed1a68c25af0c39f16d2a2d":
        raise ValueError("excluded v0.1.0 NO_GO differs")
    if pin(HERE / "review/independent-contract-go-2026-10-07.md")["sha256"] != "8db9e278caa3132f6ef5e0fd97d3aa533550ddc1ab63c658576dffaf6b592fcd":
        raise ValueError("corrected independent contract review differs")
    for relative, key in (
        ("contract.json", "contract"),
        ("evidence-2026-09-29.md", "evidence_report"),
        ("review/independent-readonly-2026-09-29.json", "independent_review"),
    ):
        if pin(ACCEPTED / relative) != contract["accepted_source"][key]:
            raise ValueError(f"accepted C04 pin differs: {relative}")
        if pin(C03 / relative) != contract["direct_c03_parent"][key]:
            raise ValueError(f"direct C03 parent pin differs: {relative}")
    author = load(HERE / "author-validation.json")
    if (
        author.get("decision") != "GO_BOUNDED"
        or author.get("checks_total") != 18094
        or author.get("checks_passed") != 18094
        or author.get("accepted_raw_seals") != 33
        or author.get("parent_raw_seals") != 11
        or author.get("failures")
    ):
        raise ValueError("author replay gate differs")
    reviewer_path = HERE / "review/independent-verdict.json"
    if not reviewer_path.exists():
        raise ValueError("separate independent postrun replay is required")
    reviewer = load(reviewer_path)
    if (
        reviewer.get("decision") != "GO_BOUNDED"
        or reviewer.get("checks") != 17325
        or reviewer.get("raw_seals") != {"c03": 11, "c04": 33}
        or reviewer.get("report_cells_per_arm") != 5210
        or reviewer.get("before_after_diff_counts") != [0, 4, 15, 0, 1, 1]
        or reviewer.get("contract_sha256") != CONTRACT_SHA
        or reviewer.get("failures")
    ):
        raise ValueError("independent replay gate differs")
    accepted_sources(contract)
    runs = []
    for arm, entry in contract["accepted_source"]["arms"].items():
        input_path = REPO / entry["input"]["path"]
        diff_path = REPO / entry["parent_diff"]["path"]
        if pin(input_path) != {k: entry["input"][k] for k in ("bytes", "sha256")}:
            raise ValueError(f"accepted input differs: {arm}")
        if pin(diff_path) != {k: entry["parent_diff"][k] for k in ("bytes", "sha256")}:
            raise ValueError(f"accepted parent diff differs: {arm}")
        run = Path(entry["local_run_dir"])
        runs.append({"role": arm, "input": entry["input"], "parent_diff": entry["parent_diff"],
                     **sealed_run(run, entry)})
    parent = contract["direct_c03_parent"]
    parent_input = REPO / parent["staffing_one_input"]["path"]
    if pin(parent_input) != {k: parent["staffing_one_input"][k] for k in ("bytes", "sha256")}:
        raise ValueError("direct C03 parent input differs")
    parent_run = Path(parent["staffing_one_run"]["local_run_dir"])
    sealed_run(parent_run, parent["staffing_one_run"])
    if sum(len(run["raw"]) for run in runs) != 33:
        raise ValueError("expected 33 final C04 raw seals")
    horizon = ACCEPTED / "runs" / contract["excluded_evidence"]["horizon_wait"]["run_id"]
    if (
        pin(horizon / "run.log") != contract["excluded_evidence"]["horizon_wait"]["run_log"]
        or (horizon / "model.sxo").stat().st_size != 4
    ):
        raise ValueError("excluded horizon-wait evidence differs")
    return {
        "schema": "simlox-c04-var02-cutoff-boundary-evidence-index/v1",
        "case_id": "C04",
        "variant_id": "C04.var02",
        "version": "0.1.1",
        "status": "bounded_read_only_classification_ready_for_publication",
        "publication_state": "not_published",
        "new_native_run_count": 0,
        "source": local_sources(HERE, HERE),
        "excluded_diagnostic_source": local_sources(EXCLUDED, HERE.parent),
        "accepted_source": {"package": ACCEPTED.name, "files": accepted_sources(contract)},
        "direct_c03_parent": parent,
        "runs": runs,
        "reused_raw_count": 33,
        "parent_raw_count": 11,
        "author_checks": author["checks_passed"],
        "independent_verdict": {"path": "review/independent-verdict.json", **pin(reviewer_path)},
        "scope": "Observed fixed-seed cutoff before/equal/after second preparation completion in three accepted C04 CLI runs.",
        "limits": "No new native behavior, universal deadline or same-time priority, general partial turnround, GUI visual, cross-engine or full Issue18 claim.",
        "raw_location_policy": "accepted_external_local_only_ignored_runs_not_committed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(raw)
    elif not destination.exists() or destination.read_bytes() != raw:
        raise ValueError("index not created; independent publication review is required before --write")
    print(json.dumps({
        "index_sha256": hashlib.sha256(raw).hexdigest(),
        "source_files": len(result["source"]),
        "reused_raw_count": result["reused_raw_count"],
        "new_native_run_count": 0,
    }))


if __name__ == "__main__":
    main()
