"""Freeze the 32 accepted IRECT count runs, raw seals, and local source pins."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT_NAMES = [f"seed-{seed:02d}-input.json" for seed in range(1, 33)]
FILES = [
    "README.md", "build.py", "cli-scope-signoff-2026-10-01.md", "contract.json",
    "panel-diff.json", "run_native_ssh.ps1", "validate.py", "validate_panel.py",
    "make_evidence_index.py", "review/author-panel-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
] + INPUT_NAMES


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    panel = load(HERE / "panel-diff.json")
    independent = load(HERE / "review/independent-readonly-2026-10-01.json")
    author = load(HERE / "review/author-panel-validation-2026-10-01.json")
    if independent.get("verdict") != "GO" or independent.get("passed") is not True or author.get("passed") is not True:
        raise ValueError("author or independent panel replay has not accepted")
    sources = {
        "contract.json": HERE / "contract.json", "build.py": HERE / "build.py",
        "validate.py": HERE / "validate.py", "validate_panel.py": HERE / "validate_panel.py", "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
        "panel-diff.json": HERE / "panel-diff.json",
        "parent-input.json": ROOT / "A03-two-aircraft-formation-v1.0.1/native-input.json",
        "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
        "manual.pdf": Path(contract["source"]["manual"]),
        **{name: HERE / name for name in INPUT_NAMES},
    }
    if sha(sources["panel-diff.json"]) != contract["panel_diff_sha256"]:
        raise ValueError("panel diff changed")
    runs = []
    for seed in contract["seeds"]:
        run = HERE / "runs" / f"j02-var02-seed{seed:02d}-v100-20261001-01"
        invocation, closure, validation = (load(run / name) for name in
                                           ("invocation.json", "closure.json", "validation.json"))
        if invocation.get("seed") != seed or closure.get("seed") != seed or validation.get("seed") != seed:
            raise ValueError(f"seed {seed} run identity differs")
        if closure.get("state") != "native_steps_complete" or validation.get("passed") is not True:
            raise ValueError(f"seed {seed} native/author replay failed")
        if closure.get("invocation_sha256") != sha(run / "invocation.json"):
            raise ValueError(f"seed {seed} invocation seal differs")
        if len(closure.get("raw", {})) != 11 or len(closure.get("post_source_sha256", {})) != len(sources):
            raise ValueError(f"seed {seed} raw/source file set differs")
        for name, path in sources.items():
            if closure["post_source_sha256"].get(name) != sha(path):
                raise ValueError(f"seed {seed} post-source seal differs: {name}")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"seed {seed} raw seal differs: {name}")
        input_name = f"seed-{seed:02d}-input.json"
        if invocation.get("input_sha256") != panel["input_sha256"][input_name]:
            raise ValueError(f"seed {seed} input hash differs")
        runs.append({
            "seed": seed, "run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"),
            "realized_count": validation["realized_count"],
            "flight_hours": validation["flight_hours"],
            "raw": closure["raw"],
        })
    evidence = {
        "schema": "simlox-j02-var02-irect-count-seed-panel-evidence-index/v1",
        "case_id": "J02", "variant_id": "J02.var02", "version": "1.0.0",
        "scope": "32 single-repetition IRECT mission-count runs with distinct fixed seeds",
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
