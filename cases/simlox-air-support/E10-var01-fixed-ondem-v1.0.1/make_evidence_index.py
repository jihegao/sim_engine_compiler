"""Seal accepted candidate E10.var01 v1.0.1 source and native closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "e10-var01-ondem-v101-ssh-20261003-01": "867fe911aa502e4fb55ae15a5488e2f6e132932f77b26ce725e552fe859e5d07",
    "e10-var01-fixed-v101-ssh-20261003-01": "97465eeda1b3a9254db3ac023988218021880253ecacc7d3be9b4854d6b0544a",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    accepted = []
    for run_id, expected in RUNS.items():
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert sha(run / "closure.json") == expected and closure["error"] is None
        assert closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        accepted.append({"run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": expected, "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    prior = HERE.parent / contract["prior_diagnostic"]["package"]
    for arm in ("fixed", "ondem"):
        assert sha(prior / "runs" / contract["prior_diagnostic"][f"{arm}_run_id"] / "closure.json") == contract["prior_diagnostic"][f"{arm}_closure_sha256"]
    result = {
        "schema": "simlox-e10-var01-v101-evidence-index/v1",
        "case_id": "E10", "variant_id": "E10.var01", "version": "1.0.1",
        "publication_state": "not_published",
        "source": source, "accepted_runs": accepted,
        "accepted_raw_count": sum(len(r["raw"]) for r in accepted),
        "parent_closure_sha256": contract["accepted_parent"]["native_closure_sha256"],
        "supporting_prerequisite_closure_sha256": contract["supporting_prerequisite"]["native_closure_sha256"],
        "prior_no_go_diagnostic_closure_sha256": {arm: contract["prior_diagnostic"][f"{arm}_closure_sha256"] for arm in ("fixed", "ondem")},
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
