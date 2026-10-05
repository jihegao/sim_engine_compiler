"""Seal all D03.var02 source versions and the existing local parent/child raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VERSIONS = [
    ROOT / "D03-var02-mission-pm-conflict-v0.1.0",
    ROOT / "D03-var02-mission-pm-conflict-v0.1.1",
    ROOT / "D03-var02-mission-pm-conflict-v0.1.2",
    HERE,
]
PARENT = ROOT / "D03-calendar-pm-v1.0.0" / "runs" / "d03-calendar-v100-ssh-20261001-02"
CHILD = VERSIONS[2] / "runs" / "d03-var02-mission245-v012-ssh-20261006-01"
OUTPUT = HERE / "evidence-index.json"
EXCLUDED = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
            "independent-publication-review-2026-10-06.md"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files() -> list[dict]:
    files = []
    for version in VERSIONS:
        for path in sorted(version.rglob("*")):
            if not path.is_file() or path.name in EXCLUDED or path.suffix == ".pyc":
                continue
            if "runs" in path.relative_to(version).parts or "__pycache__" in path.parts:
                continue
            files.append({"path": path.relative_to(ROOT).as_posix(),
                          "bytes": path.stat().st_size, "sha256": sha(path)})
    return files


def sealed(role: str, folder: Path, expected_closure: str) -> dict:
    closure_path = folder / "closure.json"
    invocation_path = folder / "invocation.json"
    assert sha(closure_path) == expected_closure, closure_path
    closure = load(closure_path)
    assert closure["error"] is None and closure["run_id"] == folder.name
    assert closure["invocation_sha256"] == sha(invocation_path)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, pin in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], path
    return {"role": role, "run_id": folder.name, "local_run_dir": str(folder.resolve()),
            "invocation": {"bytes": invocation_path.stat().st_size,
                           "sha256": sha(invocation_path)},
            "closure": {"bytes": closure_path.stat().st_size,
                        "sha256": expected_closure}, "raw": closure["raw"]}


def main() -> None:
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.3-readonly-reanalysis-candidate"
    author = load(HERE / "review" / "author-readonly-validation-2026-10-06.json")
    assert author["passed"] is True and author["checks_count"] >= 7623
    assert all(check["passed"] for check in author["checks"])
    independent = load(HERE / "review" / "independent-readonly-verdict.json")
    assert independent["verdict"] == "GO_BOUNDED_READONLY_REANALYSIS"
    assert independent["passed"] is True and independent["checks_count"] == 7546
    assert independent["failures"] == [] and independent["preserved_v012_status"] == "NO_GO_FULL_CONTRACT"
    assert load(VERSIONS[2] / "review" / "independent-verdict.json")["verdict"] == "NO_GO_FULL_CONTRACT"
    for name, path, expected in (
        ("v010 contract", VERSIONS[0] / "contract.json", contract["prior_no_go_contract"]["contract_sha256"]),
        ("v011 contract", VERSIONS[1] / "contract.json", contract["predeclared_basis"]["contract_sha256"]),
        ("v011 input", VERSIONS[1] / "native-input.json", contract["predeclared_basis"]["frozen_child_input_sha256"]),
        ("v012 contract", VERSIONS[2] / "contract.json", contract["preserved_failed_branch"]["contract_sha256"]),
        ("v012 input", VERSIONS[2] / "native-input.json", contract["sealed_run"]["input_sha256"]),
        ("v012 failed author", VERSIONS[2] / "review" / "author-native-validation-2026-10-06.json",
         contract["preserved_failed_branch"]["author_failed_verdict_sha256"]),
        ("v012 NO_GO", VERSIONS[2] / "review" / "independent-verdict.json",
         contract["preserved_failed_branch"]["independent_no_go_verdict_sha256"]),
        ("D03 parent input", ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json",
         contract["accepted_parent"]["input_sha256"]),
        ("D03 parent signoff", ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
         contract["accepted_parent"]["signoff_sha256"]),
    ):
        assert sha(path) == expected, name
    runs = [sealed("accepted_parent", PARENT, contract["accepted_parent"]["closure_sha256"]),
            sealed("sealed_diagnostic_reanalysed_readonly", CHILD, contract["sealed_run"]["closure_sha256"])]
    sources = source_files()
    assert len(sources) == len(set(item["path"] for item in sources))
    index = {
        "schema": "simlox-d03-var02-v013-readonly-evidence-index/v1",
        "case_id": "D03", "variant_id": "D03.var02", "version": "0.1.3",
        "status": "bounded_readonly_pm_first_cancellation_ready_for_publication",
        "publication_state": "not_published", "source": sources,
        "accepted_parent": contract["accepted_parent"],
        "predeclared_basis": contract["predeclared_basis"],
        "preserved_failed_branch": contract["preserved_failed_branch"],
        "runs": runs, "local_raw_count": 24,
        "author_checks": author["checks_count"],
        "independent_verdict": independent,
        "scope": "One seeded aircraft: mission identity 1 booked h23.5, CAL24 PM occupies h24-25, mission cancels h24.8333; two other missions succeed.",
        "limits": "Separate read-only application of v0.1.1 predeclared broad branch; v0.1.2 mission-first NO_GO remains excluded. No native rerun, general priority, GUI visual, cross-engine or overall Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 24,
                      "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
