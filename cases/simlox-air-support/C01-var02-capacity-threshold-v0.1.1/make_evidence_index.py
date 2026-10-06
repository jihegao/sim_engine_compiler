"""Seal C01.var02 retrospective capacity evidence, preserving both Git/local identities."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACCEPTED = ROOT / "C01-personnel-capacity-v1.0.2"
EXCLUDED = ROOT / "C01-var02-capacity-threshold-v0.1.0"
RUN_ROOT = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C01-personnel-capacity-v1.0.2/runs")
PINS = (
    ("capacity-2", "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c", "c01-v102-cap2-ssh-20260929-05", "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163"),
    ("capacity-1", "12804f3f589abddf1a4a85e27e0bdf7f965ba6750517f4de18715e7e065ba2ad", "c01-v102-cap1-ssh-20260929-04", "f8aacea0884523cc0f703bb16afc1cf08d59ae5a3dc4e7cb51c2feb377239cc5"),
    ("capacity-0", "02d1e3c1cdb585b73a00cf73b58f9d5fe6295c45c6fdc282a7c80c443499fdeb", "c01-v102-cap0-ssh-20260929-03", "722e9eab571f8a7bc32aa593fe8782b30cc182a4a196b93f0f559129f85f4dcd"),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def files(directory: Path, *, exclude_index=False) -> list:
    return sorted(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and (not exclude_index or path.name != "evidence-index.json"))


def source_pins(directory: Path, *, exclude_index=False) -> list:
    return [{"path": path.relative_to(directory).as_posix(), **pin(path)} for path in files(directory, exclude_index=exclude_index)]


def published_parent():
    paths = files(ACCEPTED)
    if len(paths) != 18:
        raise ValueError(f"accepted C01 source count differs: {len(paths)}")
    records = []
    for path in paths:
        rel = path.relative_to(ACCEPTED).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:cases/simlox-air-support/{ACCEPTED.name}/{rel}"], capture_output=True, check=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            if not (len(disk) == 8 and sha(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob):
                raise ValueError("accepted .gitignore separate disk/Git identities differ")
        elif disk != blob:
            raise ValueError(f"accepted disk/Git bytes differ: {rel}")
        records.append({"path": rel, "local_disk": pin(path), "published_git": {"bytes": len(blob), "sha256": sha(blob)}})
    return {"package": ACCEPTED.name, "files": records,
            "original_independent_review": pin(ACCEPTED / "review/independent-readonly-2026-09-29.json")}


def run_pin(variant: str, input_sha: str, run_id: str, closure_sha: str):
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
        raise ValueError(f"accepted invocation seal differs: {run_id}")
    return {"role": f"reused_accepted_{variant}", "run_id": run_id, "local_run_dir": str(run.resolve()),
            "input_sha256": input_sha, "closure": pin(closure_path), "invocation": pin(invocation), "raw": closure["raw"]}


def build():
    contract = pin(HERE / "contract.json")
    if contract["sha256"] != "1cfcfd8200a81dd9d19745770581b6d33f28096bc58c03685dc412ea183b7d6a":
        raise ValueError("v0.1.1 contract differs")
    author = load(HERE / "author-validation.json")
    if not author["passed"] or author["check_count"] != 203 or author["failures"]:
        raise ValueError("author replay differs")
    verdict = load(HERE / "review/independent-verdict.json")
    if verdict.get("decision") != "GO_BOUNDED" or verdict.get("checks_passed") != 20657 or verdict.get("checks_total") != 20657 or verdict.get("report_cells_each") != 5210 or verdict.get("accepted_raw_seals") != 33 or verdict.get("failures"):
        raise ValueError("independent replay differs")
    excluded = source_pins(EXCLUDED)
    if len(excluded) != 3 or pin(EXCLUDED / "contract.json")["sha256"] != "387e13629309cdcaa0d8a81c65fe1d0c075ecda4958636dbf8b5f5911de7f44a" or pin(EXCLUDED / "review/independent-contract-no-go-2026-10-07.md")["sha256"] != "fcccb580fb24da792141bbc692cbebd4b9766e91bbc84593629c7d2cc4619656":
        raise ValueError("excluded v0.1.0 bytes differ")
    accepted = published_parent()
    if accepted["original_independent_review"]["sha256"] != "b8b0bd11bfbde8c84e6e9bf9a4bb82a58da23e3436ce775082265d28c6d31f73":
        raise ValueError("accepted original independent review differs")
    runs = [run_pin(*entry) for entry in PINS]
    return {"schema": "simlox-c01-var02-capacity-threshold-evidence-index/v1", "case_id": "C01", "variant_id": "C01.var02", "version": "0.1.1", "status": "bounded_read_only_capacity_classification_ready_for_publication", "publication_state": "not_published", "new_native_run_count": 0,
            "source": source_pins(HERE, exclude_index=True), "excluded_v010_source": excluded,
            "accepted_source": accepted, "runs": runs, "reused_raw_count": 33,
            "author_checks": 203, "independent_verdict": {"path": "review/independent-verdict.json", **pin(HERE / "review/independent-verdict.json")},
            "scope": "One accepted fixed-seed two-P-CREW INSPECT request at capacities 2, 1 and 0, with success at capacity 2 and observed wait/cancellation at 1 and 0.",
            "limits": "Retrospective three-run classification; no new native, specialty mismatch, other demand/capacity, GUI visual, cross-engine, full C01.var02 or Issue18 claim.",
            "raw_location_policy": "accepted_external_local_only_ignored_runs_not_committed"}


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
    print(json.dumps({"index_sha256": sha(data), "source_files": len(build()["source"]), "accepted_files": 18, "excluded_files": 3, "reused_raw": 33, "new_native_runs": 0}))


if __name__ == "__main__":
    main()
