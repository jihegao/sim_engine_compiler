"""Index local, ignored native evidence without adding bulky raw files to Git."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runs = {}
    for variant in ("add", "exclude"):
        run_id = f"g03-{variant}-v101-20261001-01"
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        runs[variant] = {"run_id": run_id, "local_path": str(run), "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"), "sxo_sha256": sha(run / "model.sxo"), "raw": closure["raw"]}
    index = {"schema": "simlox-g03-base-variant-v101-evidence-index/v1", "case_id": "G03", "scope": "BSID add and QTYPM=0 exclude source acceptance with operated variant", "parent_case": "A01", "parent_source_sha256": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7", "contract_sha256": sha(HERE / "contract.json"), "builder_sha256": sha(HERE / "build.py"), "exact_diff_sha256": sha(HERE / "exact-diff.json"), "diff_checker_sha256": sha(HERE / "describe_diff.py"), "native_checker_sha256": sha(HERE / "check_roundtrip.py"), "native_runner_sha256": sha(HERE / "run_native_ssh.ps1"), "author_validator_sha256": sha(HERE / "validate_native.py"), "author_validation_sha256": sha(HERE / "author-validation-2026-10-01.json"), "independent_checker_sha256": sha(HERE / "review" / "independent_readonly.py"), "independent_report_sha256": sha(HERE / "review" / "independent-readonly-2026-10-01.json"), "installed_executable_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native_runs": runs, "limits": ["effective inherited item composition unobserved", "item failure and maintenance aggregation untested", "GUI-only behavior unverified"]}
    (HERE / "evidence-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(sha(HERE / "evidence-index.json"))


if __name__ == "__main__":
    main()
