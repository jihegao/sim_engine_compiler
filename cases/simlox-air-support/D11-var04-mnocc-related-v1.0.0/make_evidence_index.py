"""Index the corrected related-PM evidence and excluded native failure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_SHAS = {
    2: "1c724ffacc4d0a443520e91e882af1598062ce2d672913b32e278dfe62bdcb94",
    3: "685b556d620c616eab3df02c34e160349f6cf4d7038a7085ff6394ba3c470ed9",
}
FILES = [
    ".gitattributes", ".gitignore", "README.md", "build.py", "check_roundtrip.py",
    "cli-scope-signoff-2026-10-01.md", "contract.json", "describe_diff.py",
    "exact-diff.json", "make_evidence_index.py", "run_native_ssh.ps1", "validate_native.py",
    "review/independent_readonly.py", "review/static-review-2026-10-01.md",
    "failed/rejected-subtask-id-20261001/diagnosis.md",
    "failed/rejected-subtask-id-20261001/exact-diff.json",
]
for cap in INPUT_SHAS:
    FILES += [f"native-related-cap-{cap}.json",
              f"review/author-validation-related-{cap}-2026-10-01.json",
              f"review/independent-readonly-cap-{cap}-2026-10-01.json",
              f"failed/rejected-subtask-id-20261001/native-related-cap-{cap}.json"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    runs = {}
    for cap, input_sha in INPUT_SHAS.items():
        run = HERE / "runs" / f"d11-mnocc-related-{cap}-v100-ssh-20261001-02"
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        author = json.loads((HERE / f"review/author-validation-related-{cap}-2026-10-01.json").read_text())
        independent = json.loads((HERE / f"review/independent-readonly-cap-{cap}-2026-10-01.json").read_text())
        if closure.get("error") is not None or closure["run_id"] != run.name:
            raise ValueError(f"native closure invalid for cap {cap}")
        if invocation["input_sha256"] != input_sha or closure["source_hashes_before"]["input"] != input_sha:
            raise ValueError(f"source pin differs for cap {cap}")
        if closure["source_hashes_after"] != closure["source_hashes_before"]:
            raise ValueError(f"source changed during cap {cap} run")
        if closure["invocation_sha256"] != sha(run / "invocation.json"):
            raise ValueError(f"invocation seal differs for cap {cap}")
        if len(closure["raw"]) != 12:
            raise ValueError(f"raw artifact count differs for cap {cap}")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"raw seal differs for cap {cap}: {name}")
        if not author["passed"] or not independent["passed"] or independent["verdict"] != "GO":
            raise ValueError(f"review failed for cap {cap}")
        runs[str(cap)] = {
            "run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": input_sha,
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "sxo_sha256": sha(run / "model.sxo"),
            "raw": closure["raw"],
            "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
        }
    failed = HERE / "runs/d11-mnocc-related-2-v100-ssh-20261001-01"
    failed_closure = json.loads((failed / "closure.json").read_text(encoding="utf-8-sig"))
    if failed_closure["error"] != "calc output model.sxo absent/empty":
        raise ValueError("failed-run diagnosis differs")
    failed_input = "failed/rejected-subtask-id-20261001/native-related-cap-2.json"
    if failed_closure["source_hashes_before"]["input"] != sha(HERE / failed_input):
        raise ValueError("failed input source differs")
    index = {
        "schema": "simlox-d11-mnocc-related-v100-evidence-index/v1",
        "case_id": "D11", "variant_id": "D11.var04", "version": "1.0.0",
        "scope": "one related MS3 PM consuming a capped MS2 occurrence, inferred from paired native behavior",
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "accepted_runs": runs,
        "excluded_native_run": {"run_id": failed.name, "local_path": str(failed.resolve()),
                                "input_sha256": sha(HERE / failed_input),
                                "run_log_sha256": sha(failed / "run.log"),
                                "closure_sha256": sha(failed / "closure.json"),
                                "error": failed_closure["error"], "converter_error": 2011},
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(FILES), "accepted_runs": len(runs),
                      "accepted_raw_files": sum(len(r["raw"]) for r in runs.values()),
                      "excluded_runs": 1}))


if __name__ == "__main__":
    main()
