"""Seal accepted-parent lineage, disclosed diagnostics, and two fresh guarded runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "minbs1": ("e10-var06-mixed-minbs1-v103-ssh-20261003-01", "124bfff95458b07d1b3efff1b7e0c1b20da1dbcd75d6ecf02101cc2fca8ba815"),
    "minbs2": ("e10-var06-mixed-minbs2-v103-ssh-20261003-01", "047c31bea78a1ffe0dbd110d80f513df09524dbaad1eb77ae1f17152f0444ee1"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    parent_info = contract["accepted_parent"]
    parent = HERE.parent / parent_info["package"]
    assert sha(parent / "evidence-index.json") == parent_info["evidence_index_sha256"]
    for arm in RUNS:
        assert sha(parent / f"native-input-{arm}.json") == parent_info["input_sha256"][arm]
        assert sha(parent / "runs" / parent_info["run_ids"][arm] / "closure.json") == parent_info["native_closure_sha256"][arm]
    diagnostic_seals = {}
    for field in ("prior_diagnostic_no_go", "second_diagnostic_no_go", "third_diagnostic_no_go"):
        info = contract[field]
        pkg = HERE.parent / info["package"]
        for arm in RUNS:
            matches = list((pkg / "runs").glob(f"*{arm}*/closure.json"))
            assert len(matches) == 1 and sha(matches[0]) == info["native_closure_sha256"][arm]
            assert sha(pkg / f"native-input-{arm}.json") == info["input_sha256"][arm]
        diagnostic_seals[field] = {"package": info["package"], "input_sha256": info["input_sha256"], "native_closure_sha256": info["native_closure_sha256"], "publication_state": "diagnostic_no_go_local_only"}
    accepted_runs = []
    for arm, (run_id, expected) in RUNS.items():
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert sha(run / "closure.json") == expected and closure["error"] is None
        assert closure["arm"] == arm and closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        accepted_runs.append({"arm": arm, "run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": expected, "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    verdict = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8-sig"))
    assert verdict["passed"] is True and not verdict["failures"] and verdict["checks_passed"] == verdict["checks_total"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    result = {
        "schema": "simlox-e10-var06-minbs-mixed-item-v103-evidence-index/v1",
        "case_id": "E10", "variant_id": "E10.var06", "version": "1.0.3",
        "publication_state": "not_published", "source": source, "accepted_runs": accepted_runs,
        "accepted_raw_count": sum(len(r["raw"]) for r in accepted_runs),
        "parent_input_sha256": parent_info["input_sha256"],
        "parent_closure_sha256": parent_info["native_closure_sha256"],
        "parent_evidence_index_sha256": parent_info["evidence_index_sha256"],
        "disclosed_diagnostic_seals": diagnostic_seals,
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
