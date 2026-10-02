"""Bind the I02.var03 source, review, and three sealed local native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2"
RUNS = HERE / "runs"
NATIVE = RUNS / "i02-var03-between-v100-ssh-20261002-01"
DEPOT = RUNS / "i02-var03-depot-results-v100-ssh-20261002-01"
BASE = RUNS / "i02-var03-base-results-v100-ssh-20261002-01"
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "native-input.json",
    "exact-diff.json", "build.py", "describe_diff.py", "check_roundtrip.py",
    "run_native_ssh.ps1", "make_report_settings.py", "probe_depot_report_ssh.ps1",
    "probe_base_report_ssh.ps1", "validate.py", "make_evidence_index.py",
    "cli-scope-signoff-2026-10-02.md", "review/author-native-validation-2026-10-02.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-02.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder: Path, count: int) -> dict:
    closure = read(folder / "closure.json")
    assert closure["error"] is None and closure["run_id"] == folder.name
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert len(closure["raw"]) == count
    for name, seal in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"),
            "closure_sha256": sha(folder / "closure.json"), "raw": closure["raw"]}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "review/author-native-validation-2026-10-02.json")
    independent = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert contract["source_sha256"] == sha(HERE / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    assert contract["direct_parent"]["sha256"] == sha(PARENT / "native-input.json")
    assert author["passed"] and author["passed_count"] == author["check_count"] == 28
    assert independent["passed"] and independent["checks_passed"] == independent["checks_total"] == 1338
    native = run_index(NATIVE, 12)
    depot = run_index(DEPOT, 2)
    base = run_index(BASE, 2)
    assert independent["native_closure_sha256"] == native["closure_sha256"]
    assert independent["report_only_closure_sha256"]["depot"] == depot["closure_sha256"]
    assert independent["report_only_closure_sha256"]["base"] == base["closure_sha256"]
    assert independent["selected_report_sha256"]["depot"] == depot["raw"]["item-report-raw.json"]["sha256"]
    assert independent["selected_report_sha256"]["base"] == base["raw"]["item-report-raw.json"]["sha256"]
    settings = {
        "DEPOT-01": {"local_path": str((RUNS / "report-settings/item-position-results.sxs").resolve()),
                     "sha256": sha(RUNS / "report-settings/item-position-results.sxs")},
        "BASE-01": {"local_path": str((RUNS / "report-settings/base-item-position-results.sxs").resolve()),
                    "sha256": sha(RUNS / "report-settings/base-item-position-results.sxs")},
    }
    assert settings["DEPOT-01"]["sha256"] == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"
    assert settings["BASE-01"]["sha256"] == "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"
    index = {
        "schema": "simlox-i02-var03-between-v100-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var03.BETWEEN", "version": "1.0.0",
        "scope": "one available-stock zero-delay DEPOT-01 to BASE-01 transfer after accepted IN, with direct two-position stock conservation",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "direct_source_parent": {"package": PARENT.name,
                                 "source_sha256": sha(PARENT / "native-input.json"),
                                 "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md")},
        "native_runs": {"calculation": native, "depot_item_report": depot,
                        "base_item_report": base},
        "local_report_settings": settings,
        "author_validation_sha256": sha(HERE / "review/author-native-validation-2026-10-02.json"),
        "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json"),
    }
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    output = HERE / "evidence-index.json"
    if output.exists():
        assert output.read_bytes() == encoded, "frozen evidence index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 16}))


if __name__ == "__main__":
    main()
