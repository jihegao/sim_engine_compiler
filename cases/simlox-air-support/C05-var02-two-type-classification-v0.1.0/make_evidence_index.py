"""Build the C05.var02 index only after exact author and independent gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE = HERE.parent / "C05-var02-two-resource-types-v1.0.0"
PARENT = HERE.parent / "C05-mission-resource-v1.0.0"
CONTRACT_SHA = "1028e32013b7f3b655254d10c0f2cdb40529a73517326e5b5929e32639d2a7de"
CONTRACT_REVIEW_SHA = "32871b4848cf5419d8aeba43b11e800fb58be790ebff29874295495aef63e97b"
AUTHOR_SCRIPT_SHA = "181cda8588aa7148d6ebaaa36d911a6d4f3c84e5cb26a5e693fe6cf6a568eeb8"
AUTHOR_VERDICT_SHA = "0d401440b1604c9e4d59d922e993ef6da726ab67ec4411dc59c531af831008e4"
INDEPENDENT_SCRIPT_SHA = "8b03fe1d1cdcc41f7ccb434ef6a27374f31b3ad710122042652ac2b7a9b8213f"
INDEPENDENT_VERDICT_SHA = "a170870cd44562f0b8b1b12baa0bbc2fd527a076775778089f78d22aef16fc9a"
INDEPENDENT_MEMO_SHA = "7db9ae8696d86641ba8f72c2ca47fddcf6a98d25bb62185e86166a44ad88c9d1"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_pin(path: Path) -> dict:
    data = subprocess.run(
        ["git", "show", f"HEAD:{path.relative_to(REPO).as_posix()}"],
        cwd=REPO, capture_output=True, check=True,
    ).stdout
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pinned_file(name: str, expected: str):
    if pin(HERE / name)["sha256"] != expected:
        raise ValueError(f"pinned source/review changed: {name}")


def published_sources(package: Path, expected: list, count: int) -> list:
    listed = subprocess.run(
        ["git", "ls-files", "--", package.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    by_name = {item["path"]: item for item in expected}
    if len(listed) != len(by_name) or len(by_name) != count:
        raise ValueError(f"published source count differs: {package.name}")
    if {(REPO / path).relative_to(package).as_posix() for path in listed} != set(by_name):
        raise ValueError(f"published source path set differs: {package.name}")
    for name, item in by_name.items():
        path = package / name
        if pin(path) != item["local_disk"] or git_pin(path) != item["published_git"]:
            raise ValueError(f"published source bytes differ: {package.name}/{name}")
    return expected


def sealed_run(package: Path, record: dict, count: int) -> dict:
    run = package / "runs" / record["run_id"]
    if pin(run / "closure.json") != record["closure"] or pin(run / "invocation.json") != record["invocation"]:
        raise ValueError(f"run header differs: {run.name}")
    closure = read(run / "closure.json")
    if (closure["run_id"] != record["run_id"] or closure["raw"] != record["raw"]
            or closure["invocation_sha256"] != record["invocation"]["sha256"]
            or closure["source_hashes_before"] != closure["source_hashes_after"]
            or closure["source_hashes_before"] != record["source_hashes_before_after"]
            or closure["error"] is not None or len(record["raw"]) != count):
        raise ValueError(f"run closure differs: {run.name}")
    for name, expected in record["raw"].items():
        if pin(run / name) != expected:
            raise ValueError(f"raw bytes differ: {run.name}/{name}")
    return {"local_run_dir": str(run), **record}


def included(path: Path) -> bool:
    return (
        path.is_file()
        and path.name != "evidence-index.json"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-"))
    )


def build():
    for name, expected in (
        ("contract.json", CONTRACT_SHA),
        ("review/independent-contract-go-2026-10-07.md", CONTRACT_REVIEW_SHA),
        ("check_reclassification.py", AUTHOR_SCRIPT_SHA),
        ("author-validation.json", AUTHOR_VERDICT_SHA),
        ("review/independent_replay.py", INDEPENDENT_SCRIPT_SHA),
        ("review/independent-verdict.json", INDEPENDENT_VERDICT_SHA),
        ("review/independent-postrun-review-2026-10-07.md", INDEPENDENT_MEMO_SHA),
    ):
        pinned_file(name, expected)
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    reviewer = read(HERE / "review/independent-verdict.json")
    if (author.get("decision") != "GO_BOUNDED" or author.get("total_checks") != 8035
            or author.get("passed_checks") != 8035 or author.get("failures")
            or author.get("report_cells_cryptographically_pinned") != 10420
            or author.get("reused_child_raw_seals") != 24
            or author.get("direct_parent_raw_seals") != 12):
        raise ValueError("author replay gate differs")
    if (reviewer.get("decision") != "GO_BOUNDED" or reviewer.get("checks") != 14180
            or reviewer.get("contract_sha256") != CONTRACT_SHA or reviewer.get("failures")):
        raise ValueError("independent replay gate differs")
    sources = published_sources(SOURCE, contract["accepted_source"]["published_source_files"], 16)
    parent_sources = published_sources(PARENT, contract["direct_parent"]["published_source_files"], 17)
    for prereq in contract["prerequisites"].values():
        package = HERE.parent / prereq["package"]
        for name, item in prereq["pins"].items():
            path = package / name
            if pin(path) != item["local_disk"] or git_pin(path) != item["published_git"]:
                raise ValueError(f"prerequisite source changed: {package.name}/{name}")
    runs = [sealed_run(SOURCE, contract["accepted_runs"][str(capacity)], 12)
            for capacity in (2, 0)]
    parent_run = sealed_run(PARENT, contract["direct_parent"]["capacity_2_run"], 12)
    local_sources = [
        {"path": path.relative_to(HERE).as_posix(), **pin(path)}
        for path in sorted(HERE.rglob("*")) if included(path)
    ]
    return {
        "schema": "simlox-c05-var02-two-type-classification-evidence-index/v1",
        "case_id": "C05", "variant_id": "C05.var02", "version": "0.1.0",
        "status": "bounded_read_only_classification_ready_for_publication",
        "publication_state": "not_published", "new_native_run_count": 0,
        "source": local_sources,
        "accepted_source": {"package": SOURCE.name, "published_files": sources},
        "direct_parent": {"package": PARENT.name, "published_files": parent_sources,
                          "capacity_2_run": parent_run},
        "prerequisites": contract["prerequisites"],
        "runs": runs, "reused_child_raw_count": 24, "direct_parent_raw_count": 12,
        "author_checks": 8035,
        "independent_verdict": {"path": "review/independent-verdict.json",
                                **pin(HERE / "review/independent-verdict.json")},
        "scope": "Already accepted fixed C05 radio-2/radio-0 two-required-type physical and full-report evidence; no new calculation.",
        "limits": "Per-system no-partial-booking only; no formation atomicity, radio-one, one-hour catalog, other seed, GUI-only or cross-engine claim.",
        "raw_location_policy": "accepted_local_ignored_runs_not_committed",
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
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(result["source"]), "reused_child_raw_count": 24,
                      "direct_parent_raw_count": 12, "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
