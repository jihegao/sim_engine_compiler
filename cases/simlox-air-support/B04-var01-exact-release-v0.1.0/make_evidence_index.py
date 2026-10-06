"""Seal the bounded B04 exact-release child and accepted local B04 runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b04-var01-release-boundary-v010-ssh-20261006-01"
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


def accepted_run(directory, run_id, expected_closure):
    closure_path = directory / "closure.json"
    assert pin(closure_path)["sha256"] == expected_closure
    closure = load(closure_path)
    assert closure["run_id"] == run_id and not closure.get("error")
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        assert pin(directory / name) == seal, name
    return {"role": "accepted_b04", "run_id": run_id,
            "local_run_dir": str(directory.resolve()), "closure": pin(closure_path),
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
    return {"role": "bounded_b04_exact_release_child", "run_id": RUN_ID,
            "local_run_dir": str(directory.resolve()), "closure": pin(closure_path),
            "invocation": pin(directory / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    parent = contract["accepted_parent"]
    assert contract["version"] == "0.1.0-contract-candidate"
    parent_dir = ROOT / parent["package"]
    for field, filename in (
        ("turnround_input_sha256", "turnround-input.json"),
        ("control_input_sha256", "control-input.json"),
        ("contract_sha256", "contract.json"),
        ("source_diff_sha256", "exact-diff.json"),
        ("signoff_sha256", "cli-scope-signoff-2026-09-30.md"),
    ):
        assert sha(parent_dir / filename) == parent[field]
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["decision"] == "GO_BOUNDED" and author["checks"] == 4434 and not author["failures"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    assert independent["checks"] >= 4000
    runs = [
        accepted_run(parent_dir / "runs" / parent["turnround_run_id"],
                     parent["turnround_run_id"], parent["turnround_closure_sha256"]),
        accepted_run(parent_dir / "runs" / parent["control_run_id"],
                     parent["control_run_id"], parent["control_closure_sha256"]),
        child_run(),
    ]
    result = {
        "schema": "simlox-b04-var01-exact-release-evidence-index/v1",
        "case_id": "B04", "variant_id": "B04.var01", "version": "0.1.0",
        "status": "bounded_exact_release_ready_for_publication",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": parent, "runs": runs,
        "accepted_b04_raw_count": 24, "child_raw_count": 12,
        "author_checks": author["checks"], "independent_checks": independent["checks"],
        "independent_verdict": {"decision": independent["decision"],
                                "sha256": sha(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed aircraft and two waves with MissionTurnround.DURN 0.75 hour at the exact release and launch boundary.",
        "limits": "No general same-time priority, resource-constrained turnround, GUI, cross-engine, performance, full B04.var01 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 36}))


if __name__ == "__main__":
    main()
