"""Freeze J02 deterministic/boundary accepted run IDs and raw SHA-256 seals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = [
    "README.md", "build.py", "cli-scope-signoff-2026-10-01.md", "contract.json",
    "exact-diff.json", "run_native_ssh.ps1", "validate.py", "validate_panel.py",
    "make_evidence_index.py", "probe-contract.json", "probe_native_ssh.ps1",
    "review/author-panel-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
    *[f"{arm}-input.json" for arm in ("determ-2-seed-01", "determ-2-seed-02",
                                      "zero-six", "four-eight", "four-six")],
]
RUN_IDS = {
    "determ-2-seed-01": "j02-determ-2-seed01-accepted-20261001-01",
    "determ-2-seed-02": "j02-determ-2-seed02-accepted-20261001-01",
    "zero-six": "j02-zero-six-accepted-20261001-01",
    "four-eight": "j02-four-eight-accepted-20261001-01",
    "four-six": "j02-four-six-accepted-20261001-01",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    author = load(HERE / "review/author-panel-validation-2026-10-01.json")
    independent = load(HERE / "review/independent-readonly-2026-10-01.json")
    if author.get("passed") is not True or independent.get("passed") is not True or independent.get("verdict") != "GO":
        raise ValueError("author or independent replay has not accepted")
    if set(author.get("accepted_run_ids", {})) != set(RUN_IDS):
        raise ValueError("author accepted-arm matrix differs")
    runs = []
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        invocation, closure, validation, manifest = (load(run / name) for name in
            ("invocation.json", "closure.json", "validation.json", "run-manifest.json"))
        if any(record.get("arm") != arm or record.get("run_id") != run_id for record in
               (invocation, closure, validation, manifest)):
            raise ValueError(f"{arm} run identity differs")
        if closure.get("state") != "native_steps_complete" or validation.get("passed") is not True:
            raise ValueError(f"{arm} native/author replay failed")
        if closure.get("invocation_sha256") != sha(run / "invocation.json") or manifest.get("closure_sha256") != sha(run / "closure.json") or manifest.get("validation_sha256") != sha(run / "validation.json"):
            raise ValueError(f"{arm} manifest/invocation hash differs")
        if invocation.get("input_sha256") != contract["arms"][arm]["input_sha256"] or sha(run / "input.json") != contract["arms"][arm]["input_sha256"]:
            raise ValueError(f"{arm} input hash differs")
        if len(closure.get("raw", {})) != 11:
            raise ValueError(f"{arm} raw file count differs")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"{arm} raw seal differs: {name}")
        runs.append({
            "arm": arm, "run_id": run_id, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"),
            "manifest_sha256": sha(run / "run-manifest.json"),
            "activated": validation["activated"], "starts": validation["starts"],
            "successes": validation["successes"], "cancellations": validation["cancellations"],
            "flight_hours": validation["flight_hours"], "raw": closure["raw"],
        })
    evidence = {
        "schema": "simlox-j02-determ-boundary-evidence-index/v1",
        "case_id": "J02", "variant_ids": ["J02.var01", "J02.var04"], "version": "1.0.0",
        "scope": "five fresh one-repetition deterministic count/capacity arms; five diagnostic probes excluded",
        "source_files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(FILES), "native_runs": len(runs),
                      "raw_files": sum(len(run["raw"]) for run in runs)}))


if __name__ == "__main__":
    main()
