"""Index I02.var10 paired source, accepted parent and six sealed runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0"
RUNS = HERE / "runs"
ARMS = ("early", "late")
STATIONS = ("base", "depot")
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "build.py",
    "describe_diff.py", "early-input.json", "late-input.json", "exact-diff.json",
    "check_roundtrip.py", "run_native_ssh.ps1", "make_report_settings.py",
    "report_native_ssh.ps1", "validate_native.py", "author-validation.json",
    "cli-scope-signoff-2026-10-02.md", "make_evidence_index.py",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-02.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder: Path, expected: int) -> dict:
    invocation, closure = read(folder / "invocation.json"), read(folder / "closure.json")
    assert closure["error"] is None and closure["run_id"] == folder.name
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"]
    assert len(closure["raw"]) == expected
    for name, seal in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"),
            "closure_sha256": sha(folder / "closure.json"), "raw": closure["raw"]}


def main() -> None:
    contract, author = read(HERE / "contract.json"), read(HERE / "author-validation.json")
    reviewer = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert author["passed"] and author["check_count"] == len(author["checks"]) == 56
    assert reviewer["passed"] and reviewer["checks_passed"] == reviewer["checks_total"] == 895
    assert contract["direct_parent"]["source_sha256"] == sha(PARENT / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    native, reports = {}, {}
    for arm in ARMS:
        assert contract["arm_sha256"][arm] == sha(HERE / f"{arm}-input.json")
        native[arm] = run_index(RUNS / f"i02-var10-{arm}-v100-ssh-20261002-01", 12)
        reports[arm] = {}
        for station in STATIONS:
            item = run_index(RUNS / f"i02-var10-{arm}-{station}-item-v100-ssh-20261002-01", 2)
            ri = read(Path(item["local_path"]) / "invocation.json")
            assert ri["source_closure_sha256"] == native[arm]["closure_sha256"]
            assert ri["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
            reports[arm][station] = item
    selectors = {
        "base": ("base-item-position-results.sxs", "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"),
        "depot": ("item-position-results.sxs", "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"),
    }
    settings = {}
    for station, (name, expected) in selectors.items():
        path = RUNS / "report-settings" / name
        assert sha(path) == expected
        settings[station] = {"local_path": str(path.resolve()), "sha256": expected}
    index = {
        "schema": "simlox-i02-var10-target-backorder-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var10", "version": "1.0.0",
        "scope": "bounded scheduled BETWEEN arrival at target without versus with ordinary backorder",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "direct_source_parent": {
            "package": PARENT.name, "source_sha256": sha(PARENT / "native-input.json"),
            "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md"),
            "evidence_index_sha256": sha(PARENT / "evidence-index.json"),
            "native_closure_sha256": sha(PARENT / "runs/i02-var03-between-v100-ssh-20261002-01/closure.json"),
            "base_item_report_closure_sha256": sha(PARENT / "runs/i02-var03-base-results-v100-ssh-20261002-01/closure.json"),
            "depot_item_report_closure_sha256": sha(PARENT / "runs/i02-var03-depot-results-v100-ssh-20261002-01/closure.json"),
        },
        "native_runs": native, "station_reports": reports, "local_report_settings": settings,
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json"),
        "sealed_raw_file_count": 32,
    }
    output = HERE / "evidence-index.json"
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == encoded, "frozen evidence index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 32}))


if __name__ == "__main__":
    main()
