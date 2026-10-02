"""Index publication source hashes and local raw closures without copying raw data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
ACCEPTED = {
    "e15-var07-default-v101-ssh-20261002-01": "f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff",
    "e15-var07-explicit-three-v101-ssh-20261002-01": "79e4729d44a4a3ed524ad9e0f0559c4d98c3aff64278bf553c3768f956c435e5",
    "e15-var07-default-item-v101-ssh-20261002-01": "640e77479b0930137ca7f97e1f346babc9de7132ec33cd6f9ca400fb8295b249",
    "e15-var07-explicit-three-item-v101-ssh-20261002-01": "1bf91edb10034e912a49e1b810f7d5697f351a0eb50d51cefd8fa24bcdc9bbb8",
}
EXCLUDED_DIR = HERE.parent / "E15-var07-explicit-istoh-v1.0.0"
EXCLUDED = {
    "e15-var07-default-v100-ssh-20261002-01": "d4795730c82c15133e02639a24801fc8f34f9b9ccc9e300a999ca66f23d4b967",
    "e15-var07-explicit-three-v100-ssh-20261002-01": "c02b1a7470d3b432e10f6ac5ed7d129d11cf978f28fa3a9b4504dbd081ff8e3b",
    "e15-var07-default-item-v100-ssh-20261002-01": "9ea978c64f1e7d9a1521debc8f3b00292089e8468827c6cc8adb1f89d72d9939",
    "e15-var07-explicit-three-item-v100-ssh-20261002-01": "38a3ac53400f5e0f29f0d6c4b16dbc0d64b954a628b2c0fe3b68855c2745b1e0",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def indexed_runs(case: Path, expected: dict[str, str]) -> list[dict]:
    result = []
    for run_id, closure_sha in expected.items():
        run = case / "runs" / run_id
        closure_path = run / "closure.json"
        if not closure_sha or sha(closure_path) != closure_sha:
            raise ValueError(f"closure fingerprint differs: {run}")
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        invocation = run / "invocation.json"
        if closure["run_id"] != run_id or closure["invocation_sha256"] != sha(invocation) or closure["error"] is not None:
            raise ValueError(f"closure identity/error differs: {run}")
        sealed = closure["raw"]
        for name, data in sealed.items():
            path = run / name
            if not path.is_file() or path.stat().st_size != data["bytes"] or sha(path) != data["sha256"]:
                raise ValueError(f"raw seal differs: {path}")
        result.append({
            "run_id": run_id,
            "local_path": str(run.resolve()),
            "closure_sha256": closure_sha,
            "invocation_sha256": sha(invocation),
            "raw": sealed,
        })
    return result


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or "runs" in path.parts or path == OUTPUT or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    accepted = indexed_runs(HERE, ACCEPTED)
    excluded = indexed_runs(EXCLUDED_DIR, EXCLUDED)
    result = {
        "schema": "simlox-e15-var07-v101-evidence-index/v1",
        "case_id": "E15",
        "pre_run_work_label": "E15.var07",
        "catalog_variant_acceptance": "none; catalog E15.var07 explicit ISTOH above nominal not tested",
        "version": "1.0.1",
        "publication_state": "not_published",
        "source": source,
        "accepted_runs": accepted,
        "accepted_raw_count": sum(len(run["raw"]) for run in accepted),
        "excluded_diagnostic": {
            "reason": "v1.0.0 selected ItemResults absent because Item.TRACK was unset; event match alone did not meet its contract",
            "runs": excluded,
            "raw_count": sum(len(run["raw"]) for run in excluded),
        },
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "excluded_raw": result["excluded_diagnostic"]["raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
