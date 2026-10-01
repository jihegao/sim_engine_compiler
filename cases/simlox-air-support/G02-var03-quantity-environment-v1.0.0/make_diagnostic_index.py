"""Index the three excluded fixed-seed G02.var03 diagnostic raw closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ("baseline", "qty-two", "env-two")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    runs = []
    for variant in VARIANTS:
        run_id = f"g02-var03-{variant}-probe-20261002-01"
        run = HERE / "runs" / run_id
        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        assert invocation["run_id"] == closure["run_id"] == run_id
        assert invocation["variant"] == variant and closure["error"] is None
        assert sha(run / "invocation.json") == closure["invocation_sha256"]
        assert len(steps) == 5 and all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps)
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert len(closure["raw"]) == 12
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        runs.append({"run_id": run_id, "role": "excluded_diagnostic", "local_path": str(run.resolve()),
                     "invocation_sha256": sha(run / "invocation.json"),
                     "closure_sha256": sha(run / "closure.json"),
                     "input_sha256": sha(run / "input.json"),
                     "report_sha256": sha(run / "report-raw.json"),
                     "model_log_sha256": sha(run / "model.log"), "raw": closure["raw"]})
    files = sorted(p for p in HERE.rglob("*") if p.is_file()
                   and "runs" not in p.relative_to(HERE).parts
                   and "__pycache__" not in p.relative_to(HERE).parts
                   and p.name != "evidence-index.json")
    index = {"schema": "simlox-g02-var03-fixed-seed-diagnostic-index/v1", "case_id": "G02",
             "variant_id": "G02.var03", "version": "1.0.0-candidate",
             "publication_state": "excluded_diagnostic",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in files},
             "excluded_runs": runs, "reason": "one fixed-seed aggregate panel does not meet contract uncertainty requirement"}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("diagnostic index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "excluded_runs": len(runs),
                      "raw_seals": sum(len(r["raw"]) for r in runs)}))


if __name__ == "__main__":
    main()
