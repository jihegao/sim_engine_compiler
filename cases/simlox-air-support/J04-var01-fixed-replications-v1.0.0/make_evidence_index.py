"""Freeze J04.var01 current acceptance plus excluded and superseded run evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = [
    ".gitattributes", ".gitignore", "README.md", "cli-scope-signoff-2026-10-01.md",
    "build.py", "contract.json", "probe-contract.json", "probe-diff.json", "probe-input.json",
    "probe_native_ssh.ps1", "run_native_ssh.ps1", "validate.py", "validate_pair.py",
    "make_evidence_index.py", "review/author-pair-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
    "review/probe_native_ssh_unsealed_initial.ps1",
    "review/superseded-first-acceptance/contract.json",
    "review/superseded-first-acceptance/run_native_ssh.ps1",
    "review/superseded-first-acceptance/author-pair-validation-2026-10-01.json",
]
CURRENT = ("j04-var01-fixed-reps-accepted-20261001-03", "j04-var01-fixed-reps-accepted-20261001-04")
SUPERSEDED = ("j04-var01-fixed-reps-accepted-20261001-01", "j04-var01-fixed-reps-accepted-20261001-02")
PROBE = "j04-var01-fixed-reps-probe-20261001-02"
UNSEALED = "j04-var01-fixed-reps-probe-20261001-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_sealed(run_id: str, role: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if closure.get("state") != "native_steps_complete" or closure.get("run_id") != run_id or closure.get("invocation_sha256") != sha(run / "invocation.json"):
        raise ValueError(f"run identity/closure differs: {run_id}")
    parent = ROOT / "J02-var03-poisson-formation-count-v1.0.0/seed-01-input.json"
    sources = {
        "build.py": HERE / "build.py", "probe-diff.json": HERE / "probe-diff.json",
        "probe-input.json": HERE / "probe-input.json", "parent-input.json": parent,
        "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    }
    if role == "excluded_sealed_diagnostic":
        sources.update({"probe-contract.json": HERE / "probe-contract.json", "probe_native_ssh.ps1": HERE / "probe_native_ssh.ps1"})
    else:
        archive = HERE / "review/superseded-first-acceptance"
        sources.update({
            "contract.json": HERE / "contract.json" if role == "current_accepted" else archive / "contract.json",
            "run_native_ssh.ps1": HERE / "run_native_ssh.ps1" if role == "current_accepted" else archive / "run_native_ssh.ps1",
            "validate.py": HERE / "validate.py", "validate_pair.py": HERE / "validate_pair.py",
        })
        validation = load(run / "validation.json")
        if validation.get("passed") is not True:
            raise ValueError(f"run validation failed: {run_id}")
    if set(closure.get("post_source_sha256", {})) != set(sources):
        raise ValueError(f"source set differs: {run_id}")
    for name, path in sources.items():
        if closure["post_source_sha256"].get(name) != sha(path):
            raise ValueError(f"source seal differs: {run_id}/{name}")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    result = {
        "run_id": run_id, "role": role, "local_path": str(run.resolve()),
        "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"), "raw": closure["raw"],
        "report_sha256": sha(run / "report-raw.json"),
    }
    if role != "excluded_sealed_diagnostic":
        result["validation_sha256"] = sha(run / "validation.json")
    return result


def main() -> None:
    reviewer = load(HERE / "review/independent-readonly-2026-10-01.json")
    author = load(HERE / "review/author-pair-validation-2026-10-01.json")
    if reviewer.get("verdict") != "GO" or reviewer.get("passed") is not True or author.get("passed") is not True:
        raise ValueError("current accepted pair lacks author/independent GO")
    if [item["run_id"] for item in author.get("runs", [])] != list(CURRENT):
        raise ValueError("author pair binds another run")
    current = [verify_sealed(run_id, "current_accepted") for run_id in CURRENT]
    superseded = [verify_sealed(run_id, "superseded_not_published") for run_id in SUPERSEDED]
    diagnostic = verify_sealed(PROBE, "excluded_sealed_diagnostic")
    unsealed_path = HERE / "runs" / UNSEALED
    if (unsealed_path / "closure.json").exists():
        raise ValueError("first diagnostic unexpectedly has a closure")
    unsealed_files = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)} for path in unsealed_path.iterdir() if path.is_file()}
    if "report-raw.json" not in unsealed_files or "steps.json" not in unsealed_files:
        raise ValueError("unsealed diagnostic raw files missing")
    evidence = {
        "schema": "simlox-j04-var01-fixed-replications-evidence-index/v1",
        "case_id": "J04", "variant_id": "J04.var01", "version": "1.0.0",
        "scope": "two current fresh fixed-seed NREP16 accepted runs; first-only ENLOG and aggregate report; no per-replication count inference",
        "source_files_sha256": {name: sha(HERE / name) for name in FILES},
        "accepted_runs": current,
        "excluded_sealed_diagnostic": diagnostic,
        "superseded_runs": superseded,
        "excluded_unsealed_diagnostic": {
            "run_id": UNSEALED, "reason": "native steps completed but closure failed from PowerShell automatic $input in initial runner",
            "initial_runner_sha256": sha(HERE / "review/probe_native_ssh_unsealed_initial.ps1"),
            "local_path": str(unsealed_path.resolve()), "files": unsealed_files,
        },
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "current_accepted": len(current),
                      "current_raw_seals": sum(len(item["raw"]) for item in current),
                      "superseded": len(superseded), "sealed_diagnostics": 1, "unsealed_diagnostics": 1}))


if __name__ == "__main__":
    main()
