"""Seal the excluded A02 v0.1.0 failure and bounded v0.1.1 observation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "A02-var01-at-return-v0.1.0"
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-publication-review-2026-10-06.md"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def verify(path: Path, expected: str) -> None:
    assert path.is_file() and sha(path) == expected, (str(path), expected)


def source_list(folder: Path) -> list[dict]:
    result = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(folder).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(folder).as_posix(), **pin(path)})
    return result


def accepted(label: str, entry: dict) -> list[dict]:
    folder = ROOT / entry["package"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                      ("signoff", "cli-scope-signoff-2026-09-29.md"),
                      ("evidence_index", "evidence-index.json")):
        verify(folder / name, entry[f"{key}_sha256"])
    index = load(folder / "evidence-index.json")
    expected = {entry["final_run_id"]: entry["final_closure_sha256"],
                entry["replay_run_id"]: entry["replay_closure_sha256"]}
    assert len(index["runs"]) == 2
    result = []
    for run in index["runs"]:
        assert run["run_id"] in expected and len(run["artifacts"]) == 17
        for name, artifact in run["artifacts"].items():
            path = Path(artifact["path"])
            assert pin(path) == {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}, path
        verify(RAW_ROOT / label / run["run_id"] / "closure.json", expected[run["run_id"]])
        result.append({"role": f"accepted_{label.lower()}_parent" if label == "A02" else "accepted_a01_prerequisite",
                       "run_id": run["run_id"], "local_run_dir": run["directory"],
                       "artifacts": run["artifacts"]})
    assert {r["run_id"] for r in result} == set(expected)
    return result


def excluded(entry: dict) -> dict:
    folder = OLD / "runs" / entry["run_id"]
    verify(OLD / "native-input.json", entry["input_sha256"])
    verify(OLD / "check_roundtrip.py", entry["roundtrip_checker_sha256"])
    verify(folder / "closure.json", entry["closure_sha256"])
    verify(folder / "failure-seal.json", entry["failure_seal_sha256"])
    closure, seal = load(folder / "closure.json"), load(folder / "failure-seal.json")
    assert closure["error"] == "roundtrip checker exit=1" and seal["run_id"] == entry["run_id"]
    assert len(seal["files"]) == 9
    for name, artifact in seal["files"].items():
        assert pin(folder / name) == {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}, name
    return {"role": "excluded_checker_failure", "run_id": entry["run_id"],
            "local_run_dir": str(folder.resolve()), "closure": pin(folder / "closure.json"),
            "failure_seal": pin(folder / "failure-seal.json"), "raw": seal["files"],
            "native_calc_started": False, "reason": entry["reason"]}


def child(run_id: str) -> dict:
    folder = HERE / "runs" / run_id
    closure = load(folder / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(folder / name) == artifact, name
    return {"role": "bounded_at_return_child", "run_id": run_id,
            "local_run_dir": str(folder.resolve()), "closure": pin(folder / "closure.json"),
            "invocation": pin(folder / "invocation.json"), "raw": closure["raw"]}


def write(path: Path, value: dict) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.1-contract-candidate"
    author = load(HERE / "review/author-native-validation-2026-10-06.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4209 and not author["failed"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    assert independent["checks"] > 0
    parents = accepted("A01", contract["prerequisite_a01"]) + accepted("A02", contract["accepted_parent"])
    failed = excluded(contract["excluded_predecessor"])
    run_id = "a02-var01-at-return-v011-ssh-20261006-01"
    good = child(run_id)
    old_index = {"schema": "simlox-a02-var01-at-return-v010-excluded-evidence-index/v1",
                 "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.0",
                 "status": "excluded_roundtrip_checker_failure", "publication_state": "excluded_not_accepted",
                 "source": source_list(OLD), "failed_run": failed,
                 "accepted_parent": contract["accepted_parent"],
                 "prerequisite_a01": contract["prerequisite_a01"],
                 "scope": "Preserved false-negative table-count checker after native import/export; no calculation or physical result.",
                 "raw_location_policy": "local_only_ignored_runs_not_committed"}
    old_index_sha = write(OLD / "evidence-index.json", old_index)
    new_index = {"schema": "simlox-a02-var01-at-return-v011-evidence-index/v1",
                 "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.1",
                 "status": "bounded_at_return_arm_ready_for_publication", "publication_state": "not_published",
                 "source": source_list(HERE), "accepted_parent": contract["accepted_parent"],
                 "prerequisite_a01": contract["prerequisite_a01"],
                 "excluded_predecessor": {**contract["excluded_predecessor"],
                                          "evidence_index_sha256": old_index_sha},
                 "runs": parents + [failed, good], "accepted_parent_raw_count": 68,
                 "excluded_failed_raw_count": 9, "child_raw_count": 12,
                 "author_checks": author["checks_count"], "independent_checks": independent["checks"],
                 "independent_verdict": {"decision": independent["decision"],
                                         "sha256": sha(HERE / "review/independent-verdict.json")},
                 "scope": "Fixed one-aircraft A02 second mission STIM h20-to10; same-hour first return and second launch, three successful sorties and full report ledgers.",
                 "limits": "One seed and fixed mission profile; no generic same-time ordering, GUI visual, cross-engine or overall Issue18 claim.",
                 "raw_location_policy": "local_only_ignored_runs_not_committed"}
    new_index_sha = write(HERE / "evidence-index.json", new_index)
    print(json.dumps({"old_index_sha256": old_index_sha, "new_index_sha256": new_index_sha,
                      "old_source_files": len(old_index["source"]), "new_source_files": len(new_index["source"]),
                      "accepted_parent_raw": 68, "excluded_failed_raw": 9, "child_raw": 12}))


if __name__ == "__main__":
    main()
