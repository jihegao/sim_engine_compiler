"""Freeze source and local raw-run seals for the D11.var02 DTIM=1 case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {
    "probe": HERE / "runs/d11-dtim-one-probe-v100-ssh-20261001-01",
    "accepted": HERE / "runs/d11-dtim-one-v100-ssh-20261001-02",
}
FILES = [
    ".gitattributes", ".gitignore", "README.md", "build.py", "check_roundtrip.py",
    "cli-scope-signoff-2026-10-01.md", "contract.json", "describe_diff.py",
    "exact-diff.json", "make_evidence_index.py", "native-input.json",
    "probe-contract.json", "run_probe_native_ssh.ps1", "run_native_ssh.ps1",
    "validate_native.py", "review/author-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
    "review/static-review-2026-10-01.md",
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
            raise ValueError(f"{role} source changed during run")
        if closure["invocation_sha256"] != sha(run / "invocation.json"):
            raise ValueError(f"{role} invocation seal differs")
        if closure["source_hashes_before"]["input"] != sha(HERE / "native-input.json"):
            raise ValueError(f"{role} input differs")
        contract = HERE / ("probe-contract.json" if role == "probe" else "contract.json")
        runner = HERE / ("run_probe_native_ssh.ps1" if role == "probe" else "run_native_ssh.ps1")
        for key, path in (("contract", contract), ("runner_script", runner), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py")):
            if closure["source_hashes_before"][key] != sha(path):
                raise ValueError(f"{role} {key} source pin differs")
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
    if sha(RUNS["probe"] / "model.log") != sha(RUNS["accepted"] / "model.log") or sha(RUNS["probe"] / "report-raw.json") != sha(RUNS["accepted"] / "report-raw.json"):
        raise ValueError("probe and acceptance event/report bytes differ")
    author = json.loads((HERE / "review/author-validation-2026-10-01.json").read_text(encoding="utf-8"))
    independent = json.loads((HERE / "review/independent-readonly-2026-10-01.json").read_text(encoding="utf-8"))
    if not author["passed"] or not independent["passed"] or independent["verdict"] != "GO":
        raise ValueError("accepted-run review failed")
    index = {
        "schema": "simlox-d11-dtim-one-v100-evidence-index/v1",
        "case_id": "D11", "variant_id": "D11.var02", "version": "1.0.0",
        "scope": "fixed DTIM=1 six-request schedule with PM noncritical through sixth return and opportunistic work",
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
        "probe_and_acceptance_event_log_identical": True,
        "probe_and_acceptance_report_identical": True,
    }
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
