"""Freeze accepted PFAC rejection and separate cyclic-reference limitation evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = (
    ("j03-pfac-sum-accepted-20261001-01", "pfac-sum", "accepted_rejection"),
    ("j03-pfac-sum-probe-20261001-01", "pfac-sum", "excluded_diagnostic"),
    ("j03-cycle-probe-20261001-01", "cycle", "excluded_diagnostic"),
    ("j03-cycle-probe-20261001-02", "cycle", "excluded_diagnostic"),
)
FILES = [
    ".gitattributes", ".gitignore", "README.md", "cli-scope-signoff-2026-10-01.md",
    "build.py", "contract.json", "probe-contract.json", "probe-diff.json",
    "pfac-sum-input.json", "cycle-input.json", "probe_native_ssh.ps1",
    "review/probe_native_ssh_initial.ps1", "run_native_ssh.ps1",
    "validate_probes.py", "validate_pfac_acceptance.py", "make_evidence_index.py",
    "review/author-diagnostics-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    review = load(HERE / "review/independent-readonly-2026-10-01.json")
    author = load(HERE / "review/author-diagnostics-2026-10-01.json")
    accepted = load(HERE / "runs/j03-pfac-sum-accepted-20261001-01/validation.json")
    if review.get("verdict") != "GO" or review.get("passed") is not True or author.get("passed") is not True or accepted.get("passed") is not True:
        raise ValueError("author or independent review has not accepted the bounded classification")
    contract = load(HERE / "contract.json")
    probe = load(HERE / "probe-contract.json")
    runs = []
    for run_id, arm, role in RUNS:
        run = HERE / "runs" / run_id
        invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
        if closure.get("state") != "native_steps_complete" or invocation.get("arm") != arm or closure.get("arm") != arm:
            raise ValueError(f"run state/arm differs: {run_id}")
        if closure.get("invocation_sha256") != sha(run / "invocation.json"):
            raise ValueError(f"invocation seal differs: {run_id}")
        runner = (HERE / "run_native_ssh.ps1" if role == "accepted_rejection" else
                  HERE / "probe_native_ssh.ps1" if run_id.endswith("-02") else
                  HERE / "review/probe_native_ssh_initial.ps1")
        parent = (ROOT / "J03-var01-time-two-point-v1.0.0/seed-01-input.json" if arm == "pfac-sum" else
                  ROOT / "J03-var04-nested-time-v1.0.0/seed-01-input.json")
        source_paths = {
            "parent-input.json": parent,
            "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
            "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
            "probe-diff.json": HERE / "probe-diff.json", "build.py": HERE / "build.py",
            "pfac-sum-input.json": HERE / "pfac-sum-input.json", "cycle-input.json": HERE / "cycle-input.json",
        }
        if role == "accepted_rejection":
            source_paths.update({"contract.json": HERE / "contract.json", "run_native_ssh.ps1": runner,
                                 "validate_pfac_acceptance.py": HERE / "validate_pfac_acceptance.py"})
            if invocation.get("input_sha256") != contract["arms"][arm]["input_sha256"]:
                raise ValueError("accepted input fingerprint differs")
        else:
            source_paths.update({"probe-contract.json": HERE / "probe-contract.json", "probe_native_ssh.ps1": runner})
            if invocation.get("input_sha256") != probe["arms"][arm]["input_sha256"]:
                raise ValueError(f"probe input fingerprint differs: {run_id}")
        if set(closure.get("post_source_sha256", {})) != set(source_paths):
            raise ValueError(f"source file set differs: {run_id}")
        for name, path in source_paths.items():
            if closure["post_source_sha256"].get(name) != sha(path):
                raise ValueError(f"source seal differs: {run_id}/{name}")
        for name, record in closure.get("raw", {}).items():
            path = run / name
            if not path.is_file() or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"raw seal differs: {run_id}/{name}")
        temp = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)} for path in run.iterdir()
                if re.fullmatch(r"\$\d+@model\.sxi\$", path.name)}
        entry = {
            "run_id": run_id, "arm": arm, "role": role, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "runner_sha256": sha(runner),
            "calc_exit_code": load(run / "steps.json")[2]["exit_code"],
            "raw": closure["raw"], "additional_native_temp_files": temp,
        }
        if role == "accepted_rejection":
            entry["validation_sha256"] = sha(run / "validation.json")
        runs.append(entry)
    evidence = {
        "schema": "simlox-j03-negative-distribution-boundaries-evidence-index/v1",
        "case_id": "J03", "version": "1.0.0",
        "classification": {
            "J03.var05": "reusable_published: one exact PFAC-sum 0.9 native converter rejection #265, fresh accepted run",
            "J03.var06": "capability_limitation: exact cycle reproducibly crashes native calculation child 0xC00000FD in two excluded probes; no accepted simulation result",
        },
        "source_files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "source_files": len(FILES),
                      "runs": len(runs), "raw_seals": sum(len(item["raw"]) for item in runs),
                      "unsealed_native_temp_files": sum(len(item["additional_native_temp_files"]) for item in runs)}))


if __name__ == "__main__":
    main()
