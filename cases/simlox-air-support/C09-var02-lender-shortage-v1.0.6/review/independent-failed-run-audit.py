"""Read-only, standard-library audit of the excluded v106 import/export run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
RUN_ID = "c09-var02-v106-shortage-ssh-20261007-01"
RUN = CASE / "runs" / RUN_ID


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def main() -> None:
    failures: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    manifest_path = CASE / "prelaunch-manifest.json"
    manifest = obj(manifest_path)
    records = manifest["source_files"]
    check(len(records) == manifest["source_count"] == 809, "manifest record count")
    for record in records:
        path = Path(record["path"])
        check(path.is_file(), f"source missing {record['key']}")
        if path.is_file():
            check(path.stat().st_size == record["bytes"], f"source size {record['key']}")
            check(sha(path) == record["sha256"], f"source SHA {record['key']}")
    expected_map = {record["key"]: record["sha256"] for record in records}
    check(len(expected_map) == 809, "duplicate manifest keys")

    approval_path = CASE / "review" / "independent-prelaunch-go.json"
    preflight_path = CASE / "review" / "preflight-ssh0-20261007T063544146Z.json"
    approval = obj(approval_path)
    receipt = obj(preflight_path)
    invocation = obj(RUN / "invocation.json")
    closure = obj(RUN / "closure.json")
    seal = obj(RUN / "failure-seal.json")
    steps = obj(RUN / "steps.json")
    roundtrip = obj(RUN / "roundtrip-validation.json")

    check(approval["decision"] == "GO_PRELAUNCH", "approval decision")
    check(approval["manifest_sha256"] == sha(manifest_path), "approval manifest SHA")
    check(approval["preflight_sha256"] == sha(preflight_path), "approval receipt SHA")
    check(receipt["native_process_started"] is False, "preflight was not pure")
    check(invocation["run_id"] == closure["run_id"] == seal["run_id"] == RUN_ID, "run ID")
    check(invocation["manifest_sha256"] == closure["manifest_sha256"] == sha(manifest_path), "run manifest SHA")
    check(invocation["approval_sha256"] == closure["approval_sha256"] == sha(approval_path), "run approval SHA")
    check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation SHA")
    check(invocation["session_id"] == 0, "invocation SSH session")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          "protected GUI identity")
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == expected_map,
          "closure source before/after map")
    check(invocation["source_hashes_before"] == expected_map, "invocation source map")
    for name, entry in closure["raw"].items():
        path = RUN / name
        check(path.is_file(), f"closure raw missing {name}")
        if path.is_file():
            check(path.stat().st_size == entry["bytes"], f"closure raw size {name}")
            check(sha(path) == entry["sha256"], f"closure raw SHA {name}")
    check(set(closure["raw"]) == set(seal["files"]) - {"closure.json", "invocation.json"},
          "failure seal topology")
    for name, entry in seal["files"].items():
        path = RUN / name
        check(path.is_file(), f"failure seal missing {name}")
        if path.is_file():
            check(path.stat().st_size == entry["bytes"], f"failure seal size {name}")
            check(sha(path) == entry["sha256"], f"failure seal SHA {name}")
    check(len(closure["raw"]) == 8 and len(seal["files"]) == 10, "raw seal counts")
    check([step["name"] for step in steps] == ["import", "export", "check_import_export"], "step order")
    for step in steps[:2]:
        check(step["status"] == "completed" and step["exit_code"] == 0,
              f"{step['name']} native exit")
        check(step["child_session_id"] == 0 and step["gui_preserved"] is True,
              f"{step['name']} session and GUI")
    check(steps[2]["status"] == "failed" and steps[2]["exit_code"] is None,
          "checker null exit and failure")
    check(steps[2]["child_session_id"] == 0 and steps[2]["gui_preserved"] is True,
          "checker session and GUI")
    check(steps[2]["error"] == closure["error"] == seal["error"], "error lineage")
    check(roundtrip["passed"] is True and roundtrip["issues"] == []
          and roundtrip["authored_row_tables"] == 25, "roundtrip content")
    check(roundtrip["source_sha256"] == sha(RUN / "input.json")
          and roundtrip["export_sha256"] == sha(RUN / "roundtrip-raw.json"),
          "roundtrip input/export SHA")
    check((RUN / "check_import_export-stderr.txt").stat().st_size == 0, "checker stderr empty")
    for name in ("model.sxo", "model.log", "run.log", "report-raw.json", "author-validation.json"):
        check(not (RUN / name).exists(), f"unexpected later artifact {name}")
    check(closure["publication_state"] == "not_published" and seal["publication_state"] == "excluded",
          "excluded state")

    verdict = {
        "decision": "NO_GO_RUN" if not failures else "NO_GO_AUDIT",
        "run_id": RUN_ID,
        "manifest_sha256": sha(manifest_path),
        "approval_sha256": sha(approval_path),
        "preflight_sha256": sha(preflight_path),
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "failure_seal_sha256": sha(RUN / "failure-seal.json"),
        "source_records_checked": len(records),
        "closure_raw_checked": len(closure["raw"]),
        "failure_seal_files_checked": len(seal["files"]),
        "roundtrip_passed_content_only": roundtrip["passed"],
        "checker_exit_code": steps[2]["exit_code"],
        "calc_or_report_started": False,
        "failures": failures,
    }
    print(json.dumps(verdict, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
