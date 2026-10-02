"""Bind the matched zero-source pair and six sealed local native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0"
RUNS = HERE / "runs"
NATIVE = {"control": RUNS / "i02-var05-zero-control-v100-ssh-20261002-01",
          "zero": RUNS / "i02-var05-zero-child-v100-ssh-20261002-01"}
REPORT = {(arm, station): RUNS / f"i02-var05-zero-{arm}-{station}-v100-ssh-20261002-01"
          for arm in NATIVE for station in ("depot", "base")}
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "build.py", "control-input.json",
    "native-input.json", "describe_diff.py", "exact-diff.json", "contract.json",
    "check_roundtrip_control.py", "check_roundtrip_zero.py",
    "run_control_native_ssh.ps1", "run_zero_native_ssh.ps1", "make_report_settings.py",
    "probe_control_depot_report_ssh.ps1", "probe_control_base_report_ssh.ps1",
    "probe_zero_depot_report_ssh.ps1", "probe_zero_base_report_ssh.ps1",
    "validate.py", "make_evidence_index.py", "cli-scope-signoff-2026-10-02.md",
    "review/author-native-validation-2026-10-02.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-02.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder: Path, count: int) -> dict:
    c = read(folder / "closure.json")
    assert c["error"] is None and c["run_id"] == folder.name
    assert c["source_hashes_before"] == c["source_hashes_after"]
    assert c["invocation_sha256"] == sha(folder / "invocation.json")
    assert len(c["raw"]) == count
    assert all((folder / name).stat().st_size == seal["bytes"]
               and sha(folder / name) == seal["sha256"]
               for name, seal in c["raw"].items())
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"),
            "closure_sha256": sha(folder / "closure.json"), "raw": c["raw"]}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "review/author-native-validation-2026-10-02.json")
    independent = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert contract["accepted_parent"]["source_sha256"] == sha(PARENT / "native-input.json")
    assert contract["control_sha256"] == sha(HERE / "control-input.json")
    assert contract["source_sha256"] == sha(HERE / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    assert author["passed"] and author["passed_count"] == author["check_count"] == 34
    assert independent["passed"] and independent["checks_passed"] == independent["checks_total"]
    native = {arm: run_index(folder, 12) for arm, folder in NATIVE.items()}
    reports = {f"{arm}_{station}": run_index(folder, 2)
               for (arm, station), folder in REPORT.items()}
    selectors = {
        "DEPOT-01": (RUNS / "report-settings/item-position-results.sxs",
                     "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"),
        "BASE-01": (RUNS / "report-settings/base-item-position-results.sxs",
                    "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"),
    }
    assert all(sha(path) == expected for path, expected in selectors.values())
    index = {
        "schema": "simlox-i02-var05-zero-source-v100-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var05.zero-source", "version": "1.0.0",
        "scope": "matched h2 one-unit BETWEEN before h4 IN: available-one control vs zero-source child; h2 transfer backorder and h4 completion, target nominal ahead of physical arrival",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "accepted_source_parent": {"package": PARENT.name,
                                   "source_sha256": sha(PARENT / "native-input.json"),
                                   "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md")},
        "native_runs": native, "station_reports": reports,
        "local_report_settings": {station: {"local_path": str(path.resolve()), "sha256": expected}
                                  for station, (path, expected) in selectors.items()},
        "author_validation_sha256": sha(HERE / "review/author-native-validation-2026-10-02.json"),
        "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json"),
    }
    raw = (json.dumps(index, indent=2) + "\n").encode()
    output = HERE / "evidence-index.json"
    if output.exists():
        assert output.read_bytes() == raw, "frozen evidence index differs"
    else:
        output.write_bytes(raw)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 32,
                      "source_files": len(SOURCES)}))


if __name__ == "__main__":
    main()
