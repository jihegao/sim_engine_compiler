"""Seal the B05.var06 read-only classification and both accepted B05.var03 runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE.parent / "B05-var03-predefined-inspect-v1.0.0"
PINS = (
    ("ordinary-control-input.json", "37423c0c127a014d082c740780eee8531e877c405bcd537918b8fc1e4289892b", "b05-var03-ordinary-20260930-01", "f8edd2fa92e8dc68e37a87b7f457b9fe644e89baa963424ab9a34eaf2ee14245"),
    ("predefined-inspect-input.json", "2fc3b10f9a17db8dc4cc4fa4810d79ef9231775c1fcb658303742ad15e41fc46", "b05-var03-predefined-20260930-01", "e47ddd60c4ccba0750ddebacd948a1feedfcb46322eb6f288d82843d2b3fdad4"),
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha_bytes(data)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files() -> list:
    return [{"path": path.relative_to(HERE).as_posix(), **pin(path)} for path in sorted(HERE.rglob("*")) if path.is_file() and path.name != "evidence-index.json" and "__pycache__" not in path.parts and path.suffix != ".pyc"]


def accepted_files() -> list:
    out = []
    files = [path for path in ACCEPTED.rglob("*") if path.is_file() and "runs" not in path.parts and "__pycache__" not in path.parts]
    if len(files) != 16:
        raise ValueError(f"accepted source file count differs: {len(files)}")
    for path in sorted(files):
        rel = path.relative_to(ACCEPTED).as_posix()
        disk = path.read_bytes()
        git_path = f"cases/simlox-air-support/{ACCEPTED.name}/{rel}"
        blob = subprocess.run(["git", "show", f"HEAD:{git_path}"], check=True, capture_output=True).stdout
        if disk != blob:
            raise ValueError(f"accepted disk/Git bytes differ: {rel}")
        out.append({"path": rel, "disk": pin(path), "published_git": {"bytes": len(blob), "sha256": sha_bytes(blob)}})
    return out


def accepted_run(input_name: str, input_sha: str, run_id: str, closure_sha: str) -> dict:
    if pin(ACCEPTED / input_name)["sha256"] != input_sha:
        raise ValueError(f"accepted input differs: {input_name}")
    directory = ACCEPTED / "runs" / run_id
    closure_path = directory / "closure.json"
    if pin(closure_path)["sha256"] != closure_sha:
        raise ValueError(f"accepted closure differs: {run_id}")
    closure = load(closure_path)
    if closure["run_id"] != run_id or closure["error"] is not None or len(closure["raw"]) != 12:
        raise ValueError(f"accepted run identity/error/raw count differs: {run_id}")
    for name, seal in closure["raw"].items():
        if pin(directory / name) != {"bytes": seal["bytes"], "sha256": seal["sha256"]}:
            raise ValueError(f"accepted raw seal differs: {run_id}/{name}")
    invocation = directory / "invocation.json"
    if pin(invocation)["sha256"] != closure["invocation_sha256"]:
        raise ValueError(f"accepted invocation differs: {run_id}")
    return {"role": "reused_accepted_b05_var03", "run_id": run_id, "input_file": input_name,
            "local_run_dir": str(directory.resolve()), "closure": pin(closure_path),
            "invocation": pin(invocation), "raw": closure["raw"]}


def build() -> dict:
    contract = pin(HERE / "contract.json")
    author = load(HERE / "author-validation.json")
    verdict = load(HERE / "review/independent-verdict.json")
    if contract["sha256"] != "7a87b8d51a44b6fc0e5ed03324e6ac362eac8ca1b264a9644b7b9a55b3122706":
        raise ValueError("frozen contract differs")
    if not author["passed"] or author["check_count"] != 108 or author["failures"]:
        raise ValueError("author replay differs")
    if verdict.get("decision") != "GO_BOUNDED" or verdict.get("checks_passed") != 12704 or verdict.get("checks_total") != 12704 or verdict.get("report_cells_each") != 4044 or verdict.get("failures"):
        raise ValueError("independent replay differs")
    if pin(ACCEPTED / "review/independent-readonly-2026-09-30.json")["sha256"] != "ac7ce7fda400db5a6a60d73a21d9dea43b226f5894dbbd6df956c5ec9dd44c4b":
        raise ValueError("accepted original independent review differs")
    sources = accepted_files()
    runs = [accepted_run(*values) for values in PINS]
    return {"schema": "simlox-b05-var06-ordinary-custom-evidence-index/v1", "case_id": "B05", "variant_id": "B05.var06", "version": "0.1.0",
            "status": "bounded_read_only_ordinary_custom_sutid_classification_ready_for_publication", "publication_state": "not_published", "new_native_run_count": 0,
            "source": source_files(), "accepted_source": {"package": ACCEPTED.name, "files": sources,
            "original_independent_report": pin(ACCEPTED / "review/independent-readonly-2026-09-30.json")},
            "runs": runs, "reused_raw_count": 24, "author_checks": 108,
            "independent_verdict": {"path": "review/independent-verdict.json", **pin(HERE / "review/independent-verdict.json")},
            "scope": "One ordinary custom INSPECT preparation row binds through native import/export and performs its authored 1/6-hour work before a successful mission; predefined <INSPECT> is an accepted contrast.",
            "limits": "Retrospective fixed-seed reuse only: no new run, other identifiers or task types, GUI visual, cross-engine, full B05.var06 or Issue18 claim.",
            "raw_location_policy": "accepted_local_only_ignored_runs_not_committed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(data)
    elif destination.read_bytes() != data:
        raise ValueError("frozen evidence index differs")
    print(json.dumps({"index_sha256": sha_bytes(data), "new_source_files": len(build()["source"]),
                      "accepted_source_files": 16, "reused_raw_count": 24, "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
