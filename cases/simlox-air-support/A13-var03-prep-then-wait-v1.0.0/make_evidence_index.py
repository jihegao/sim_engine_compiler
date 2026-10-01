"""Freeze A13.var03 source pins and local native raw evidence seals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {
    "diagnostic_control": HERE / "runs/a13-var03-prep-control-v100-20261001-01",
    "diagnostic_dependency": HERE / "runs/a13-var03-prep-dependency-v100-20261001-01",
    "accepted_control": HERE / "runs/a13-var03-prep-control-v100-20261001-02",
    "accepted_dependency": HERE / "runs/a13-var03-prep-dependency-v100-20261001-02",
}
SOURCES = {
    "parent": ROOT / "A13-start-dependence-v1.0.0/dependent-input.json",
    "structure": ROOT / "B01-fixed-preparation-v1.0.1/native-input.json",
    "contract": HERE / "contract.json",
    "builder": HERE / "build.py",
    "exact_diff": HERE / "exact-diff.json",
    "diff_checker": HERE / "describe_diff.py",
    "checker": HERE / "check_roundtrip.py",
    "runner_script": HERE / "run_native_ssh.ps1",
}
FILES = [
    "README.md", "build.py", "check_roundtrip.py",
    "cli-scope-signoff-2026-10-01.md", "contract.json", "control-input.json",
    "dependency-input.json", "describe_diff.py", "exact-diff.json", "make_evidence_index.py",
    "run_native_ssh.ps1", "validate.py", "review/pre-run-2026-10-01.md",
    "review/author-validation-2026-10-01.json", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-01.json", "review/static-review-2026-10-01.md",
    "failed/validator-spacing-20261001/validate-precorrection.py",
    "failed/validator-spacing-20261001/author-replay-failure.json",
    "failed/validator-spacing-20261001/diagnosis.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    runs = {}
    for role, run in RUNS.items():
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        if closure.get("error") is not None or closure["run_id"] != run.name:
            raise ValueError(f"{role} closure invalid")
        if closure["source_hashes_before"] != closure["source_hashes_after"]:
            raise ValueError(f"{role} source changed during execution")
        if closure["invocation_sha256"] != sha(run / "invocation.json"):
            raise ValueError(f"{role} invocation seal differs")
        variant = "control" if role.endswith("control") else "dependency"
        if closure["source_hashes_before"]["input"] != sha(HERE / f"{variant}-input.json"):
            raise ValueError(f"{role} input differs")
        for key, path in SOURCES.items():
            if closure["source_hashes_before"][key] != sha(path):
                raise ValueError(f"{role} {key} source pin differs")
        validator = HERE / ("failed/validator-spacing-20261001/validate-precorrection.py" if role.startswith("diagnostic_") else "validate.py")
        if closure["source_hashes_before"]["validator"] != sha(validator):
            raise ValueError(f"{role} validator pin differs")
        if len(closure["raw"]) != 12:
            raise ValueError(f"{role} raw artifact count differs")
        for name, seal in closure["raw"].items():
            path = run / name
            if path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
                raise ValueError(f"{role} raw seal differs: {name}")
        runs[role] = {"run_id": run.name, "local_path": str(run.resolve()),
                      "input_sha256": invocation["input_sha256"],
                      "invocation_sha256": sha(run / "invocation.json"),
                      "closure_sha256": sha(run / "closure.json"),
                      "sxo_sha256": sha(run / "model.sxo"), "raw": closure["raw"]}
    author = json.loads((HERE / "review/author-validation-2026-10-01.json").read_text(encoding="utf-8-sig"))
    independent = json.loads((HERE / "review/independent-readonly-2026-10-01.json").read_text(encoding="utf-8-sig"))
    if not author["passed"] or not independent["passed"] or independent["verdict"] != "GO":
        raise ValueError("accepted-run reviews failed")
    index = {"schema": "simlox-a13-var03-prep-wait-v100-evidence-index/v1", "case_id": "A13",
             "variant_id": "A13.var03", "version": "1.0.0",
             "scope": "positive FOLLOW preparation completes before START wait; fixed same-unit pair",
             "files_sha256": {name: sha(HERE / name) for name in FILES}, "runs": runs,
             "diagnostic_runs_excluded_from_acceptance": True}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(FILES), "native_runs": len(runs),
                      "raw_files": sum(len(r["raw"]) for r in runs.values())}))


if __name__ == "__main__":
    main()
