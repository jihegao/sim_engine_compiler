"""Seal the C01.var01 read-only specialty comparison without copying raw runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE.parent / "C01-personnel-capacity-v1.0.2"
RUN_ROOT = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C01-personnel-capacity-v1.0.2/runs")
PINS = (
    ("qualified", "capacity-2", "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c", "c01-v102-cap2-ssh-20260929-05", "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163"),
    ("wrong_specialty", "wrong-specialty", "e1341e7abfc8e1f4c853ba11648c0dfb1de6a90de3341aecae180af8ea4d0783", "c01-v102-wrong-ssh-20260929-03", "610b2b9d12352a9ca06f9241c2d20f824bfa759fffd0a6f202d2ee1b4a44ba8f"),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def new_source():
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and path.name != "evidence-index.json" and "__pycache__" not in path.parts and path.suffix != ".pyc")
    return [{"path": path.relative_to(HERE).as_posix(), **pin(path)} for path in files]


def accepted_source():
    files = sorted(path for path in ACCEPTED.rglob("*") if path.is_file() and "runs" not in path.parts and "__pycache__" not in path.parts)
    if len(files) != 18:
        raise ValueError(f"accepted source file count differs: {len(files)}")
    records = []
    for path in files:
        rel = path.relative_to(ACCEPTED).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:cases/simlox-air-support/{ACCEPTED.name}/{rel}"], check=True, capture_output=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            if not (len(disk) == 8 and sha(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob):
                raise ValueError("accepted .gitignore dual identities differ")
        elif disk != blob:
            raise ValueError(f"accepted disk/Git bytes differ: {rel}")
        records.append({"path": rel, "local_disk": pin(path), "published_git": {"bytes": len(blob), "sha256": sha(blob)}})
    return {"package": ACCEPTED.name, "files": records,
            "original_independent_review": pin(ACCEPTED / "review/independent-readonly-2026-09-29.json")}


def accepted_run(role: str, variant: str, input_sha: str, run_id: str, closure_sha: str):
    if pin(ACCEPTED / "inputs" / f"{variant}.json")["sha256"] != input_sha:
        raise ValueError(f"accepted input differs: {variant}")
    run = RUN_ROOT / run_id
    closure_path = run / "closure.json"
    if pin(closure_path)["sha256"] != closure_sha:
        raise ValueError(f"accepted closure differs: {run_id}")
    closure = load(closure_path)
    if closure["run_id"] != run_id or closure["variant_id"] != variant or len(closure["raw"]) != 11:
        raise ValueError(f"accepted run identity/raw count differs: {run_id}")
    for name, sealed in closure["raw"].items():
        if pin(run / name) != {"bytes": sealed["bytes"], "sha256": sealed["sha256"]}:
            raise ValueError(f"accepted raw seal differs: {run_id}/{name}")
    invocation = run / "invocation.json"
    if pin(invocation)["sha256"] != closure["invocation_sha256"]:
        raise ValueError(f"accepted invocation differs: {run_id}")
    return {"role": role, "variant": variant, "run_id": run_id, "local_run_dir": str(run.resolve()),
            "input_sha256": input_sha, "closure": pin(closure_path), "invocation": pin(invocation), "raw": closure["raw"]}


def build():
    if pin(HERE / "contract.json")["sha256"] != "6ccf6608d3b1c86f0463f9414bf890536d81ed4b94c8672a132701c5eb8b377c":
        raise ValueError("contract differs")
    author = load(HERE / "author-validation.json")
    verdict = load(HERE / "review/independent-verdict.json")
    if author.get("decision") != "GO_BOUNDED" or author.get("check_count") != 147 or author.get("failures"):
        raise ValueError("author replay differs")
    if verdict.get("decision") != "GO_BOUNDED" or verdict.get("checks_passed") != 11079 or verdict.get("checks_total") != 11079 or verdict.get("raw_seals") != 22 or verdict.get("report_cells_each") != 5210 or verdict.get("failures"):
        raise ValueError("independent replay differs")
    accepted = accepted_source()
    if accepted["original_independent_review"]["sha256"] != "b8b0bd11bfbde8c84e6e9bf9a4bb82a58da23e3436ce775082265d28c6d31f73":
        raise ValueError("original independent review differs")
    runs = [accepted_run(*entry) for entry in PINS]
    return {"schema": "simlox-c01-var01-personnel-specialty-evidence-index/v1", "case_id": "C01", "variant_id": "C01.var01", "version": "0.1.0", "status": "bounded_read_only_specialty_classification_ready_for_publication", "publication_state": "not_published", "new_native_run_count": 0,
            "source": new_source(), "accepted_source": accepted, "runs": runs, "reused_raw_count": 22,
            "author_checks": 147, "independent_verdict": {"path": "review/independent-verdict.json", **pin(HERE / "review/independent-verdict.json")},
            "scope": "One accepted fixed-seed two-person P-CREW INSPECT demand with equal total SPECIAL capacity but qualified P-CREW versus P-OTHER allocation.",
            "limits": "Retrospective two-run classification only: no new native, general substitution/specialty policy, shifts, contention, GUI visual, cross-engine, full C01.var01 or Issue18 claim.",
            "raw_location_policy": "accepted_external_local_only_ignored_runs_not_committed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    dest = HERE / "evidence-index.json"
    if args.write:
        if dest.exists():
            raise FileExistsError(dest)
        dest.write_bytes(raw)
    elif dest.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    print(json.dumps({"index_sha256": sha(raw), "new_source_files": len(build()["source"]), "accepted_source_files": 18, "reused_raw_count": 22, "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
