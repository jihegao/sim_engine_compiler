"""Build the C05.var01 index only after both read-only replay gates pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ACCEPTED = HERE.parent / "C05-mission-resource-v1.0.0"
CONTRACT_SHA = "096c4a6d23079c46416e06b8d79229033a13ecc23db29eb1ea6c2bf2524390ad"
CONTRACT_REVIEW_SHA = "af1005ad25d1ca9905ef74f127c050bf630e06adf33bf798b594d062f9f088f0"
AUTHOR_SCRIPT_SHA = "0d3c09962c7e99e514ebe29f763da4dc0853b6d1b6e9f73a9c404ed56c867f74"
AUTHOR_VERDICT_SHA = "16af10a2f351a58dac181da663ddf1c9f31f5c9203fb5f1b4299c12707e920b4"
INDEPENDENT_SCRIPT_SHA = "a13bc421940b2ec1ad681388ecc9009ef9a20c3976af3ea2b1f7defc5db934b3"
INDEPENDENT_VERDICT_SHA = "7ac920b9f2815e92a0d7430d95fb2678e4e1da8f0e328e7a2b418cc27c313e31"
INDEPENDENT_MEMO_SHA = "5345725cc6668f2ba973fe4385df6b626045a1fc7f980c1020620dbc00d8d951"


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


def require_sha(relative: str, expected: str):
    path = HERE / relative
    if pin(path)["sha256"] != expected:
        raise ValueError(f"pinned review/source changed: {relative}")


def accepted_source(contract: dict) -> list[dict]:
    files = contract["accepted_source"]["published_source_files"]
    listed = subprocess.run(
        ["git", "ls-files", "--", ACCEPTED.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    if len(files) != len(listed) or len(files) != 17:
        raise ValueError("accepted source file count differs")
    expected = {item["path"]: item for item in files}
    names = {(REPO / item).relative_to(ACCEPTED).as_posix() for item in listed}
    if names != set(expected):
        raise ValueError("accepted source path set differs")
    for name, record in expected.items():
        path = ACCEPTED / name
        if pin(path) != record["local_disk"] or git_pin(path) != record["published_git"]:
            raise ValueError(f"accepted source changed: {name}")
    for prerequisite in contract["prerequisites"].values():
        package = HERE.parent / prerequisite["package"]
        for name, record in prerequisite["pins"].items():
            path = package / name
            if pin(path) != record["local_disk"] or git_pin(path) != record["published_git"]:
                raise ValueError(f"accepted prerequisite changed: {path}")
    return files


def accepted_runs(contract: dict) -> list[dict]:
    output = []
    for capacity in (2, 1, 0):
        record = contract["accepted_runs"][str(capacity)]
        run = ACCEPTED / "runs" / record["run_id"]
        if pin(run / "closure.json") != record["closure"] or pin(run / "invocation.json") != record["invocation"]:
            raise ValueError(f"accepted run header changed: {capacity}")
        closure = read(run / "closure.json")
        if (closure["run_id"] != record["run_id"] or closure["raw"] != record["raw"]
                or closure["source_hashes_before"] != closure["source_hashes_after"]
                or closure["source_hashes_before"] != record["source_hashes_before_after"]
                or closure["error"] is not None or len(record["raw"]) != 12):
            raise ValueError(f"accepted run closure differs: {capacity}")
        for name, expected in record["raw"].items():
            if pin(run / name) != expected:
                raise ValueError(f"accepted raw changed: {capacity}/{name}")
        output.append({"capacity": capacity, "local_run_dir": str(run), **record})
    return output


def included(path: Path) -> bool:
    return (
        path.is_file()
        and path.name != "evidence-index.json"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-"))
    )


def build():
    for path, expected in (
        ("contract.json", CONTRACT_SHA),
        ("review/independent-contract-go-2026-10-07.md", CONTRACT_REVIEW_SHA),
        ("check_reclassification.py", AUTHOR_SCRIPT_SHA),
        ("author-validation.json", AUTHOR_VERDICT_SHA),
        ("review/independent_replay.py", INDEPENDENT_SCRIPT_SHA),
        ("review/independent-verdict.json", INDEPENDENT_VERDICT_SHA),
        ("review/independent-postrun-review-2026-10-07.md", INDEPENDENT_MEMO_SHA),
    ):
        require_sha(path, expected)
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-verdict.json")
    if (author.get("decision") != "GO_BOUNDED" or author.get("total_checks") != 15059
            or author.get("passed_checks") != 15059 or author.get("failures")
            or author.get("report_cells_cryptographically_pinned") != 15630):
        raise ValueError("author replay gate differs")
    if (independent.get("decision") != "GO_BOUNDED" or independent.get("checks") != 21056
            or independent.get("contract_sha256") != CONTRACT_SHA or independent.get("failures")):
        raise ValueError("independent replay gate differs")
    source_files = accepted_source(contract)
    runs = accepted_runs(contract)
    local_source = [
        {"path": path.relative_to(HERE).as_posix(), **pin(path)}
        for path in sorted(HERE.rglob("*")) if included(path)
    ]
    return {
        "schema": "simlox-c05-var01-resource-capacity-evidence-index/v1",
        "case_id": "C05", "variant_id": "C05.var01", "version": "0.1.0",
        "status": "bounded_read_only_classification_ready_for_publication",
        "publication_state": "not_published", "new_native_run_count": 0,
        "source": local_source,
        "accepted_source": {"package": ACCEPTED.name, "published_files": source_files},
        "prerequisites": contract["prerequisites"],
        "runs": runs, "reused_raw_count": 36,
        "author_checks": 15059,
        "independent_verdict": {"path": "review/independent-verdict.json",
                                **pin(HERE / "review/independent-verdict.json")},
        "scope": "Existing fixed C05 two-aircraft mission-crew capacity 2/1/0 physical and full-report classification only.",
        "limits": "No new native behavior, one-hour catalog example, general capacity law, other seed/resource type, GUI-only or cross-engine claim.",
        "raw_location_policy": "accepted_local_ignored_runs_not_committed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(data)
    elif not destination.exists() or destination.read_bytes() != data:
        raise ValueError("index not created; publication review is required before --write")
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "reused_raw_count": 36,
                      "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
