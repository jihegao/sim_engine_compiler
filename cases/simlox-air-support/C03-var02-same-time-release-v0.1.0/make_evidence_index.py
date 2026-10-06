"""Build the C03.var02 source index only after independent postrun replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ACCEPTED = HERE.parent / "C03-shared-crew-formation-v1.0.2"
STAFFING = HERE.parent / "C03-var01-staffing-v0.1.1"
CONTRACT_SHA = "5c441afe4cd33bfda4a955e4df90bff442b923a40d7e3981692be609a748ba05"


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


def local_sources() -> list[dict]:
    return [
        {"path": path.relative_to(HERE).as_posix(), **pin(path)}
        for path in sorted(HERE.rglob("*"))
        if included(path)
    ]


def accepted_sources(contract) -> list[dict]:
    prefix = ACCEPTED.relative_to(REPO).as_posix()
    listed = subprocess.run(
        ["git", "ls-files", "--", prefix], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    expected = {item["path"]: item for item in contract["accepted_source"]["published_source_files"]}
    if len(listed) != len(expected) or len(expected) != 16:
        raise ValueError("accepted C03 published source set differs")
    for relative in listed:
        path = REPO / relative
        name = path.relative_to(ACCEPTED).as_posix()
        record = expected[name]
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative.replace(chr(92), '/')}"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        if pin(path) != record["local_disk"]:
            raise ValueError(f"accepted C03 local source differs: {name}")
        if {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} != record["published_git"]:
            raise ValueError(f"accepted C03 Git source differs: {name}")
        if name != ".gitignore" and path.read_bytes() != blob:
            raise ValueError(f"accepted C03 source byte divergence: {name}")
        if name == ".gitignore" and path.read_bytes().replace(b"\r\n", b"\n") != blob:
            raise ValueError("accepted C03 .gitignore exception differs")
    return contract["accepted_source"]["published_source_files"]


def accepted_runs(contract) -> list[dict]:
    result = []
    for role, arm in contract["accepted_source"]["arms"].items():
        source = REPO / arm["input_path"]
        run = Path(arm["raw_location"])
        if pin(source) != arm["input"] or pin(run / "closure.json") != arm["closure"]:
            raise ValueError(f"accepted {role} source/closure differs")
        closure = load(run / "closure.json")
        if closure["run_id"] != arm["run_id"] or len(closure["raw"]) != 11 or closure["raw"] != arm["raw"]:
            raise ValueError(f"accepted {role} closure raw map differs")
        if pin(run / "invocation.json") != arm["invocation"] or closure["invocation_sha256"] != arm["invocation"]["sha256"]:
            raise ValueError(f"accepted {role} invocation differs")
        for name, seal in arm["raw"].items():
            if pin(run / name) != seal:
                raise ValueError(f"accepted {role} raw seal differs: {name}")
        result.append({
            "role": role,
            "run_id": arm["run_id"],
            "input": {"path": arm["input_path"], **arm["input"]},
            "local_run_dir": str(run),
            "closure": arm["closure"],
            "invocation": arm["invocation"],
            "raw": arm["raw"],
        })
    return result


def build():
    if pin(HERE / "contract.json")["sha256"] != CONTRACT_SHA:
        raise ValueError("frozen contract differs")
    contract = load(HERE / "contract.json")
    for relative, key in (
        ("contract.json", "contract"),
        ("evidence-2026-09-29.md", "evidence_report"),
        ("review/independent-readonly-2026-09-29.json", "original_independent_review"),
    ):
        if pin(ACCEPTED / relative) != contract["accepted_source"][key]:
            raise ValueError(f"accepted C03 pin differs: {relative}")
    for relative, key in (
        ("contract.json", "contract"),
        ("evidence-index.json", "evidence_index"),
        ("cli-scope-signoff-2026-10-07.md", "scope_signoff"),
        ("review/independent-verdict.json", "independent_verdict"),
    ):
        if pin(STAFFING / relative) != contract["published_staffing_parent"][key]:
            raise ValueError(f"published C03.var01 pin differs: {relative}")
    if pin(HERE / "review/independent-contract-2026-10-07.md")["sha256"] != "2adbab57984b3ef79ae5292b40710e2c9d37423260de092f0173952cdb80d627":
        raise ValueError("independent contract review differs")
    author = load(HERE / "author-validation.json")
    if (
        author.get("decision") != "GO_BOUNDED"
        or author.get("checks_total") != 16582
        or author.get("checks_passed") != 16582
        or author.get("raw_seals") != 22
        or author.get("failures")
    ):
        raise ValueError("author replay gate differs")
    reviewer_path = HERE / "review/independent-verdict.json"
    if not reviewer_path.exists():
        raise ValueError("separate independent postrun replay is required")
    reviewer = load(reviewer_path)
    if (
        reviewer.get("decision") != "GO_BOUNDED"
        or reviewer.get("checks") != 11732
        or reviewer.get("accepted_raw_seals") != 22
        or reviewer.get("report_cells_compared") != 10420
        or reviewer.get("failures")
    ):
        raise ValueError("independent replay gate differs")
    runs = accepted_runs(contract)
    if sum(len(run["raw"]) for run in runs) != 22:
        raise ValueError("expected 22 reused raw seals")
    return {
        "schema": "simlox-c03-var02-same-time-release-evidence-index/v1",
        "case_id": "C03",
        "variant_id": "C03.var02",
        "version": "0.1.0",
        "status": "bounded_read_only_classification_ready_for_publication",
        "publication_state": "not_published",
        "new_native_run_count": 0,
        "source": local_sources(),
        "accepted_source": {"package": ACCEPTED.name, "files": accepted_sources(contract)},
        "published_staffing_parent": contract["published_staffing_parent"],
        "runs": runs,
        "reused_raw_count": 22,
        "author_checks": author["checks_passed"],
        "independent_verdict": {"path": "review/independent-verdict.json", **pin(reviewer_path)},
        "scope": "Observed h8 release, waiting-task retest, regrant and work in accepted one-crew C03 run, with accepted two-crew capacity control.",
        "limits": "Overlaps C03.var01; no new native behavior, general same-time scheduling or fairness rule, GUI visual, cross-engine or full Issue18 claim.",
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
