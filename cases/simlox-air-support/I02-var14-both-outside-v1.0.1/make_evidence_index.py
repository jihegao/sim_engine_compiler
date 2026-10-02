"""Index accepted I02.var14 raw evidence and the excluded initial probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2"
NATIVE = HERE / "runs/i02-var14-both-outside-v101-ssh-20261002-01"
REPORT = HERE / "runs/i02-var14-depot-item-v101-ssh-20261002-01"
PROBE = HERE.parent / "I02-var14-both-outside-v1.0.0/runs/i02-var14-both-outside-v100-ssh-20261002-01"
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "build.py",
    "describe_diff.py", "native-input.json", "exact-diff.json", "check_roundtrip.py",
    "run_native_ssh.ps1", "make_report_settings.py", "report_native_ssh.ps1",
    "validate_native.py", "author-validation.json", "cli-scope-signoff-2026-10-02.md",
    "make_evidence_index.py", "update_publication_index.py",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-02.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder: Path, expected_count: int, expected_error: str | None = None) -> dict:
    inv, closure = read(folder / "invocation.json"), read(folder / "closure.json")
    assert closure["run_id"] == folder.name and closure["error"] == expected_error
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"]
    assert len(closure["raw"]) == expected_count
    for name, seal in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"),
            "closure_sha256": sha(folder / "closure.json"),
            "raw": closure["raw"], "error": closure["error"]}


def main() -> None:
    contract, author = read(HERE / "contract.json"), read(HERE / "author-validation.json")
    reviewer = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert author["passed"] and author["passed_count"] == author["check_count"] == 24
    assert reviewer["passed"] and reviewer["checks_passed"] == reviewer["checks_total"] == 511
    assert sha(HERE / "native-input.json") == contract["input_sha256"]
    assert sha(PARENT / "native-input.json") == contract["direct_parent"]["source_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    native = run_index(NATIVE, 12)
    report = run_index(REPORT, 2)
    probe = run_index(PROBE, 9, "nonzero converter error count absent")
    assert probe["closure_sha256"] == "2b1526c8b16aae6825457ec7bcea6011c631af4ba515e8c29c80b5c949f0f8e0"
    assert read(REPORT / "invocation.json")["source_closure_sha256"] == native["closure_sha256"]
    assert read(REPORT / "invocation.json")["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
    selector = HERE / "runs/report-settings/item-position-results.sxs"
    assert sha(selector) == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"
    index = {
        "schema": "simlox-i02-var14-both-outside-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var14", "version": "1.0.1",
        "scope": "bounded installed-CLI silent handling of one manual-prohibited double-OUTSIDE row",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "direct_source_parent": {
            "package": PARENT.name,
            "source_sha256": sha(PARENT / "native-input.json"),
            "signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md"),
            "evidence_index_sha256": sha(PARENT / "evidence-index.json"),
            "native_closure_sha256": sha(PARENT / "runs/i02-var01-in-v102-ssh-20261002-01/closure.json"),
            "item_report_closure_sha256": sha(PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01/closure.json"),
        },
        "accepted_native_run": native,
        "accepted_depot_item_report": report,
        "accepted_raw_file_count": 14,
        "excluded_initial_probe": probe,
        "excluded_probe_raw_file_count": 9,
        "local_report_settings": {"local_path": str(selector.resolve()), "sha256": sha(selector)},
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json"),
    }
    output = HERE / "evidence-index.json"
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == encoded, "frozen evidence index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "accepted_raw_files": 14,
                      "excluded_probe_raw_files": 9}))


if __name__ == "__main__":
    main()
