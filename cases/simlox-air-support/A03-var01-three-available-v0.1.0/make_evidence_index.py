"""Seal the bounded A03 three-available child and its accepted native parent."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "a03-var01-three-avail-v010-ssh-20261006-01"
PARENT_RUN = Path(
    "C:/Users/user/Documents/Codex/2026-09-28/simlox-issue18-ssh-current/"
    "cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/"
    "runs/a03-v101-ssh-gui-20260929-01"
)
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-publication-review-2026-10-06.md"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def source_files():
    result = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return result


def parent_run(entry):
    directory = PARENT_RUN
    closure_path = directory / "closure.json"
    assert sha(closure_path) == entry["closure_sha256"]
    closure = load(closure_path)
    assert closure["run_id"] == entry["run_id"] and not closure.get("error")
    assert len(closure["raw"]) == 11
    for name, seal in closure["raw"].items():
        assert pin(directory / name) == seal, name
    return {"role": "accepted_a03", "run_id": entry["run_id"],
            "local_run_dir": str(directory), "closure": pin(closure_path),
            "raw": closure["raw"]}


def child_run():
    directory = HERE / "runs" / RUN_ID
    closure_path = directory / "closure.json"
    closure = load(closure_path)
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(directory / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        assert pin(directory / name) == seal, name
    return {"role": "bounded_a03_three_available_child", "run_id": RUN_ID,
            "local_run_dir": str(directory.resolve()), "closure": pin(closure_path),
            "invocation": pin(directory / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    accepted = contract["accepted_parent"]
    parent = ROOT / accepted["package"]
    for field, filename in (
        ("input_sha256", "native-input.json"),
        ("contract_sha256", "contract.json"),
        ("signoff_sha256", "cli-scope-signoff-2026-09-29.md"),
        ("independent_review_sha256", "review/independent-readonly-2026-09-29.json"),
    ):
        assert sha(parent / filename) == accepted[field]
    prereq = contract["instructional_prerequisite"]
    a02 = ROOT / "A02-single-aircraft-repeated-missions"
    assert sha(a02 / "native-input.json") == prereq["input_sha256"]
    assert sha(a02 / "cli-scope-signoff-2026-09-29.md") == prereq["signoff_sha256"]
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["decision"] == "GO_BOUNDED" and author["checks"] == 4498 and not author["failures"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    assert independent["checks"] >= 3000
    result = {
        "schema": "simlox-a03-var01-three-available-evidence-index/v1",
        "case_id": "A03", "variant_id": "A03.var01", "version": "0.1.0",
        "status": "bounded_three_available_ready_for_publication",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": accepted, "instructional_prerequisite": prereq,
        "runs": [parent_run(accepted), child_run()],
        "accepted_a03_raw_count": 11, "child_raw_count": 12,
        "author_checks": author["checks"], "independent_checks": independent["checks"],
        "independent_verdict": {"decision": independent["decision"],
                                "sha256": sha(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed A03 wave with three ready aircraft against MissionType.NOS=MNOS=2; exactly two allocated and one left ready.",
        "limits": "No larger fleet, alternate selection priority, faults, GUI, cross-engine, performance, full A03.var01 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 23}))


if __name__ == "__main__":
    main()
