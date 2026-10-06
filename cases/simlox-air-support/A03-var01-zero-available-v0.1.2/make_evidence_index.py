"""Seal the bounded A03 zero-availability child and both excluded diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "a03-var01-zero-v012-ssh-20261006-01"
SOURCE_PACKAGES = (
    ROOT / "A03-var01-zero-available-v0.1.0",
    ROOT / "A03-var01-zero-available-v0.1.1",
    HERE,
)
EXCLUDE = {
    "evidence-index.json", "cli-scope-signoff-2026-10-06.md",
    "independent-publication-review-2026-10-06.md",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    result = []
    for package in SOURCE_PACKAGES:
        for path in sorted(package.rglob("*")):
            if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
                continue
            if "runs" in path.relative_to(package).parts or "__pycache__" in path.parts:
                continue
            result.append({"path": path.relative_to(HERE).as_posix() if path.is_relative_to(HERE)
                           else "../" + package.name + "/" + path.relative_to(package).as_posix(),
                           **pin(path)})
    return result


def sealed_run(package, run_id, expected_closure_sha, expected_raw, role):
    directory = package / "runs" / run_id
    closure_path = directory / "closure.json"
    assert sha(closure_path) == expected_closure_sha
    closure = load(closure_path)
    assert closure["run_id"] == run_id and len(closure["raw"]) == expected_raw
    for name, seal in closure["raw"].items():
        assert pin(directory / name) == seal, (role, name)
    return {"role": role, "run_id": run_id, "local_run_dir": str(directory.resolve()),
            "closure": pin(closure_path), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.2-contract-candidate"
    accepted = contract["accepted_parent"]
    parent = ROOT / accepted["package"]
    for key, name in (
        ("input_sha256", "native-input.json"),
        ("contract_sha256", "contract.json"),
        ("signoff_sha256", "cli-scope-signoff-2026-10-06.md"),
        ("evidence_index_sha256", "evidence-index.json"),
        ("independent_verdict_sha256", "review/independent-verdict.json"),
    ):
        assert sha(parent / name) == accepted[key]
    parent_run = sealed_run(parent, accepted["run_id"], accepted["closure_sha256"],
                            12, "accepted_a03_one_of_two_parent")
    assert load(parent / "runs" / accepted["run_id"] / "closure.json")["error"] is None

    zero_v010, zero_v011, _ = SOURCE_PACKAGES
    d010 = contract["excluded_v010_diagnostic"]
    for key, name in (("input_sha256", "native-input.json"),
                      ("contract_sha256", "contract.json"),
                      ("runner_sha256", "run_native_ssh.ps1")):
        assert sha(zero_v010 / name) == d010[key]
    v010 = sealed_run(zero_v010, d010["run_id"], d010["closure_sha256"],
                      10, "excluded_v010_converter_gate")
    assert load(zero_v010 / "runs" / d010["run_id"] / "closure.json")["error"] == "converter diagnostics differ"
    failure_path = zero_v010 / "runs" / d010["run_id"] / "failure-seal.json"
    assert sha(failure_path) == d010["failure_seal_sha256"]
    failure = load(failure_path)
    assert failure["run_id"] == d010["run_id"] and len(failure["files"]) == 12
    for name, seal in failure["files"].items():
        assert pin(failure_path.parent / name) == seal, ("v010_failure", name)
    v010["failure_seal"] = pin(failure_path)
    v010["failure_files"] = failure["files"]
    for key, name in (("run_log_sha256", "run.log"), ("model_log_sha256", "model.log")):
        assert sha(failure_path.parent / name) == d010[key]

    d011 = contract["excluded_v011_diagnostic"]
    for key, name in (("input_sha256", "native-input.json"),
                      ("contract_sha256", "contract.json"),
                      ("runner_sha256", "run_native_ssh.ps1"),
                      ("validator_sha256", "validate_native_cli.py"),
                      ("author_validation_sha256", "review/author-validation.json"),
                      ("independent_diagnostic_sha256", "review/independent-diagnostic-2026-10-06.md")):
        assert sha(zero_v011 / name) == d011[key]
    v011 = sealed_run(zero_v011, d011["run_id"], d011["closure_sha256"],
                      12, "excluded_v011_ftmo_gate")
    assert load(zero_v011 / "runs" / d011["run_id"] / "closure.json")["error"] is None
    assert sha(zero_v011 / "runs" / d011["run_id"] / "report-raw.json") == d011["report_sha256"]
    old_author = load(zero_v011 / "review/author-validation.json")
    assert old_author["decision"] == "NO_GO" and old_author["checks"] == 4445
    assert len(old_author["failures"]) == 72 and all("FTMO zero" in item for item in old_author["failures"])

    child_dir = HERE / "runs" / RUN_ID
    child = sealed_run(HERE, RUN_ID, sha(child_dir / "closure.json"), 12,
                       "bounded_v012_zero_available_child")
    child_closure = load(child_dir / "closure.json")
    assert child_closure["error"] is None
    assert child_closure["source_hashes_before"] == child_closure["source_hashes_after"]
    assert child_closure["invocation_sha256"] == sha(child_dir / "invocation.json")
    child["invocation"] = pin(child_dir / "invocation.json")
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["decision"] == "GO_BOUNDED" and author["checks"] == 4639 and not author["failures"]
    assert independent["decision"] == "GO_BOUNDED" and independent["checks"] == 4545 and not independent["failures"]
    result = {
        "schema": "simlox-a03-var01-zero-available-evidence-index/v1",
        "case_id": "A03", "variant_id": "A03.var01", "version": "0.1.2",
        "status": "bounded_zero_available_ready_for_publication",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": accepted,
        "excluded_diagnostics": [d010, d011],
        "runs": [parent_run, v010, v011, child],
        "raw_counts": {"accepted_parent": 12, "excluded_v010_closure": 10,
                       "excluded_v010_failure": 12, "excluded_v011": 12, "child": 12},
        "author_checks": author["checks"], "independent_checks": independent["checks"],
        "independent_verdict": {"decision": independent["decision"],
                                "sha256": sha(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed h8 A03 mission with explicit QTYPS0, NOS=MNOS2; demand cancels without physical allocation.",
        "limits": "Earlier v0.1.0/v0.1.1 diagnostics remain NO_GO; no omitted-deployment, alternate availability, GUI, cross-engine, full A03.var01 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_seals": 58}))


if __name__ == "__main__":
    main()
