"""Seal C02.var02 retrospective equipment-zero evidence and original raw chain."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE.parent / "C02-joint-resources-v1.0.2"
RUN_ROOT = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C02-joint-resources-v1.0.2/runs")
PINS = (
    ("available", "serial-both", "f7b9c19958d96cdc8a6bf955fd94a52e61b12e6dd116e310683732688dbf550e", "c02-v102-serial-both-ssh-20260929-02", "86c0de86b8494953d39704aafe64f6aab7038e2a649d684a926739b399670c84"),
    ("equipment_zero", "serial-equipment-zero", "2f209a5420432263b588230624d7586a3edecab2da613efbf65d6a1e8df862fa", "c02-v102-serial-zero-ssh-20260929-02", "79ab8014a50ed3797a537d8395c9ba1a60b97eb27be26b187e5c93860bbe6d64"),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def new_source():
    paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p.name != "evidence-index.json" and "__pycache__" not in p.parts and p.suffix != ".pyc")
    return [{"path": p.relative_to(HERE).as_posix(), **pin(p)} for p in paths]


def accepted_source():
    paths = sorted(p for p in ACCEPTED.rglob("*") if p.is_file() and "runs" not in p.parts and "__pycache__" not in p.parts)
    if len(paths) != 18:
        raise ValueError(f"accepted C02 source count differs: {len(paths)}")
    files = []
    for path in paths:
        rel = path.relative_to(ACCEPTED).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:cases/simlox-air-support/{ACCEPTED.name}/{rel}"], capture_output=True, check=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            if not (len(disk) == 8 and sha(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob):
                raise ValueError("accepted .gitignore local/Git identities differ")
        elif disk != blob:
            raise ValueError(f"accepted local/Git bytes differ: {rel}")
        files.append({"path": rel, "local_disk": pin(path), "published_git": {"bytes": len(blob), "sha256": sha(blob)}})
    return {"package": ACCEPTED.name, "files": files,
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
    if pin(HERE / "contract.json")["sha256"] != "475f5d05aec01c27e57cbe2c2afd7fc77e3f60c5dd0e33783b834d7de2b5ba56":
        raise ValueError("contract differs")
    author = load(HERE / "author-validation.json")
    verdict = load(HERE / "review/independent-verdict.json")
    if author.get("decision") != "GO_BOUNDED" or author.get("check_count") != 53 or author.get("failures"):
        raise ValueError("author replay differs")
    if verdict.get("decision") != "GO_BOUNDED" or verdict.get("checks_passed") != 11252 or verdict.get("checks_total") != 11252 or verdict.get("raw_seals") != 22 or verdict.get("report_cells_each") != 5210 or verdict.get("failures"):
        raise ValueError("independent replay differs")
    accepted = accepted_source()
    if accepted["original_independent_review"]["sha256"] != "6a2ee36473b85de15c72fc896375afb050d6cec60572a5fd4e46d64a56af4264":
        raise ValueError("accepted original independent review differs")
    runs = [accepted_run(*entry) for entry in PINS]
    return {"schema": "simlox-c02-var02-equipment-zero-evidence-index/v1", "case_id": "C02", "variant_id": "C02.var02", "version": "0.1.0", "status": "bounded_read_only_equipment_zero_classification_ready_for_publication", "publication_state": "not_published", "new_native_run_count": 0,
            "source": new_source(), "accepted_source": accepted, "runs": runs, "reused_raw_count": 22,
            "author_checks": 53, "independent_verdict": {"path": "review/independent-verdict.json", **pin(HERE / "review/independent-verdict.json")},
            "scope": "One accepted serial two-resource INSPECT demand with P-CREW1 available and E-GSE capacity one versus zero; available arm works and succeeds, device-zero arm waits and cancels.",
            "limits": "Retrospective two-run classification only; no new native, personnel-zero, general all-or-none or deadline policy, substitution, shifts, contention, GUI visual, cross-engine, full C02.var02 or Issue18 claim.",
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
    print(json.dumps({"index_sha256": sha(raw), "source_files": len(build()["source"]), "accepted_source_files": 18, "reused_raw_count": 22, "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
