"""Index original ignored G03 native runs by ID, byte length, and SHA-256."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ("base-control", "add-inherited", "add-extra", "exclude-base")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    runs = {}
    for variant in VARIANTS:
        run_id = f"g03-effective-{variant}-v100-20261001-01"
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        runs[variant] = {"run_id": run_id, "local_path": str(run), "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"), "sxo_sha256": sha(run / "model.sxo"), "raw": closure["raw"]}
    index = {"schema": "simlox-g03-effective-item-evidence-index/v1", "case_id": "G03", "scope": "fixed-seed BSID base/inherited/added/excluded LRU contrast", "parents": contract["parents"], "contract_sha256": sha(HERE / "contract.json"), "builder_sha256": sha(HERE / "build.py"), "exact_diff_sha256": sha(HERE / "exact-diff.json"), "diff_checker_sha256": sha(HERE / "describe_diff.py"), "native_checker_sha256": sha(HERE / "check_roundtrip.py"), "native_runner_sha256": sha(HERE / "run_native_ssh.ps1"), "author_validator_sha256": sha(HERE / "validate_native.py"), "author_report_sha256": sha(HERE / "author-validation-2026-10-01.json"), "installed_executable_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native_runs": runs}
    reviewer = HERE / "review"
    if (reviewer / "independent_readonly.py").is_file() and (reviewer / "independent-readonly-2026-10-01.json").is_file():
        index["independent_checker_sha256"] = sha(reviewer / "independent_readonly.py")
        index["independent_report_sha256"] = sha(reviewer / "independent-readonly-2026-10-01.json")
    (HERE / "evidence-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(sha(HERE / "evidence-index.json"))


if __name__ == "__main__":
    main()
