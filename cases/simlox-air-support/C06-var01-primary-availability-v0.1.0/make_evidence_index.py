"""Build C06.var01 source index only after exact independent replay pins exist."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE = HERE.parent / "C06-alternative-resource-v1.0.0"
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2"
CONTRACT_SHA = "63e5f70f9e7556d5ec3282c5c2346ffecc6b6b336f6f03cc703d18fe6a929535"
CONTRACT_REVIEW_SHA = "e5ff8023097f7cb39cdeca8f7530246bf9a179d6e49a29253363bc6477bc23c3"
AUTHOR_SCRIPT_SHA = "450433a626854c2b8cc184ed8ca8afbc7f3c04ddd5369ff960a1bf28814157e3"
AUTHOR_VERDICT_SHA = "1132f7dfec4103a4aaa09f38e97e33f96e8b247aa466c472bf522afe5b93a33e"
INDEPENDENT_SCRIPT_SHA = "9e084291bd3b7b7bcbd5b9bf01f6c1f3fc130d996a82d75b980890d152815c46"
INDEPENDENT_VERDICT_SHA = "708c0a84447c3e7393cf0f5a1fa87396aa2f66b894b0c32446c4715385e4f48b"
INDEPENDENT_MEMO_SHA = "ca280881a31def7c62cf62bd11d829285befce48a568a3de1510b50457e1fedd"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_pin(path: Path) -> dict:
    data = subprocess.run(
        ["git", "show", "HEAD:" + path.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, check=True,
    ).stdout
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def required(path: Path, expected_sha: str):
    if expected_sha is None or len(expected_sha) != 64 or pin(path)["sha256"] != expected_sha:
        raise ValueError("missing or changed exact gate: " + str(path))


def published_files(package: Path, record: dict, expected_count: int):
    tracked = subprocess.run(
        ["git", "ls-files", "--", package.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    files = record["source_files"]
    if len(tracked) != len(files) or len(files) != expected_count:
        raise ValueError("published file count changed: " + package.name)
    if {(REPO / item).relative_to(package).as_posix() for item in tracked} != set(files):
        raise ValueError("published path set changed: " + package.name)
    for name, item in files.items():
        path = package / name
        if pin(path) != item["local_disk"] or git_pin(path) != item["published_git"]:
            raise ValueError("accepted published source changed: " + str(path))
    return record


def sealed_run(record: dict, expected_count: int):
    folder = Path(record["path"])
    if pin(folder / "closure.json") != record["closure"] or pin(folder / "invocation.json") != record["invocation"]:
        raise ValueError("accepted run header changed: " + folder.name)
    closure = read(folder / "closure.json")
    if closure["raw"] != record["raw"] or len(record["raw"]) != expected_count:
        raise ValueError("accepted raw map changed: " + folder.name)
    if closure["invocation_sha256"].lower() != record["invocation"]["sha256"]:
        raise ValueError("accepted invocation link changed: " + folder.name)
    if expected_count == 12:
        if (closure["source_hashes_before"] != closure["source_hashes_after"]
                or closure["source_hashes_before"] != record["source_hashes_before"]):
            raise ValueError("C06 source map changed: " + folder.name)
    elif closure["input_sha256"] != record["input_sha256"]:
        raise ValueError("C03 input changed: " + folder.name)
    for name, item in record["raw"].items():
        if pin(folder / name) != item:
            raise ValueError("accepted raw bytes changed: " + folder.name + "/" + name)
    return record


def include(path: Path) -> bool:
    return (path.is_file() and path.name != "evidence-index.json" and
            "__pycache__" not in path.parts and path.suffix != ".pyc" and
            not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-")))


def build():
    for name, digest in [
        ("contract.json", CONTRACT_SHA),
        ("review/independent-contract-go-2026-10-07.md", CONTRACT_REVIEW_SHA),
        ("check_reclassification.py", AUTHOR_SCRIPT_SHA),
        ("author-validation.json", AUTHOR_VERDICT_SHA),
        ("review/independent_replay.py", INDEPENDENT_SCRIPT_SHA),
        ("review/independent-verdict.json", INDEPENDENT_VERDICT_SHA),
        ("review/independent-postrun-review-2026-10-07.md", INDEPENDENT_MEMO_SHA),
    ]:
        required(HERE / name, digest)
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-verdict.json")
    if (author.get("decision") != "GO_BOUNDED" or author.get("total_checks") != 13313
            or author.get("passed_checks") != 13313 or author.get("failures")
            or author.get("report_cells_checked") != 10420
            or author.get("accepted_C06_raw_seals") != 24
            or author.get("accepted_C03_parent_raw_seals") != 11):
        raise ValueError("author replay gate differs")
    if (independent.get("decision") != "GO_BOUNDED" or independent.get("checks") != 14192
            or independent.get("contract_sha256") != CONTRACT_SHA or independent.get("failures")):
        raise ValueError("independent replay gate differs")
    accepted = published_files(SOURCE, contract["accepted_C06_source"], 17)
    parent = published_files(PARENT, contract["accepted_C03_parent"], 16)
    parent_run = sealed_run(parent["staffing_2_run"], 11)
    pair = {name: sealed_run(record, 12)
            for name, record in contract["accepted_C06_runs"].items()}
    local = [{"path": path.relative_to(HERE).as_posix(), **pin(path)}
             for path in sorted(HERE.rglob("*")) if include(path)]
    return {
        "schema": "simlox-c06-var01-primary-availability-evidence-index/v1",
        "case_id": "C06", "variant_id": "C06.var01", "version": "0.1.0",
        "publication_state": "not_published", "new_native_run_count": 0,
        "status": "bounded_read_only_classification_ready_for_publication",
        "source": local,
        "accepted_source": accepted,
        "accepted_C03_parent": {**parent, "staffing_2_run": parent_run},
        "accepted_C06_runs": pair,
        "accepted_C06_raw_count": 24, "accepted_C03_raw_count": 11,
        "author_checks": 13313,
        "independent_verdict": {"path": "review/independent-verdict.json",
                                **pin(HERE / "review/independent-verdict.json")},
        "scope": "Accepted C06 primary-two/primary-zero ARTF-two CLI evidence; no new calculation.",
        "limits": "One two-aircraft mission and primary/alternative pair; no general fallback, ARTF, stochastic, GUI-only or cross-engine law.",
        "raw_location_policy": "accepted_local_ignored_runs_not_committed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    output = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(output)
    elif not destination.exists() or destination.read_bytes() != output:
        raise ValueError("index absent; independent publication review required before --write")
    print(json.dumps({"sha256": hashlib.sha256(output).hexdigest(),
                      "source_count": len(result["source"]), "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
