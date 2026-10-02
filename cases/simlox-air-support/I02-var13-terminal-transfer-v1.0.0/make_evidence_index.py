"""Index two accepted parents, six source-bound closures and 32 raw files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ARMS = ("transit", "backorder")
STATIONS = ("depot", "base")
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "build.py",
    "describe_diff.py", "transit-input.json", "backorder-input.json", "exact-diff.json",
    "check_roundtrip.py", "run_native_ssh.ps1", "make_report_settings.py",
    "report_native_ssh.ps1", "validate_native.py", "author-validation.json",
    "cli-scope-signoff-2026-10-02.md", "make_evidence_index.py",
    "update_publication_index.py", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-02.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder: Path, expected: int) -> dict:
    inv, closed = read(folder / "invocation.json"), read(folder / "closure.json")
    assert closed["error"] is None and closed["run_id"] == folder.name
    assert closed["invocation_sha256"] == sha(folder / "invocation.json")
    assert closed["source_hashes_before"] == closed["source_hashes_after"] == inv["source_hashes_before"]
    assert len(closed["raw"]) == expected
    for name, seal in closed["raw"].items():
        path = folder / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"),
            "closure_sha256": sha(folder / "closure.json"), "raw": closed["raw"]}


def main() -> None:
    contract, author = read(HERE / "contract.json"), read(HERE / "author-validation.json")
    reviewer = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert author["passed"] and author["passed_count"] == author["check_count"] == 48
    assert reviewer["passed"] and reviewer["checks_passed"] == reviewer["checks_total"] == 420
    assert reviewer["raw_seals_checked"] == 32
    native, reports, parents = {}, {}, {}
    for arm in ARMS:
        cfg = contract["arms"][arm]
        parent = HERE.parent / cfg["accepted_parent"]
        assert sha(parent) == cfg["parent_sha256"]
        assert sha(HERE / f"{arm}-input.json") == cfg["input_sha256"]
        package = parent.parent
        parents[arm] = {"package": package.name, "source_sha256": sha(parent),
                        "signoff_sha256": sha(package / "cli-scope-signoff-2026-10-02.md"),
                        "evidence_index_sha256": sha(package / "evidence-index.json")}
        native[arm] = run_index(RUNS / f"i02-var13-{arm}-v100-ssh-20261002-01", 12)
        reports[arm] = {}
        for station in STATIONS:
            indexed = run_index(RUNS / f"i02-var13-{arm}-{station}-item-v100-ssh-20261002-01", 2)
            inv = read(Path(indexed["local_path"]) / "invocation.json")
            assert inv["source_closure_sha256"] == native[arm]["closure_sha256"]
            assert inv["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
            reports[arm][station] = indexed
    selectors = {
        "depot": ("item-position-results.sxs", "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"),
        "base": ("base-item-position-results.sxs", "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"),
    }
    settings = {}
    for station, (filename, expected) in selectors.items():
        path = RUNS / "report-settings" / filename
        assert sha(path) == expected
        settings[station] = {"local_path": str(path.resolve()), "sha256": expected}
    index = {
        "schema": "simlox-i02-var13-terminal-transfer-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var13", "version": "1.0.0",
        "scope": "bounded terminal in-transit and log-visible transfer backorder under zero mission initiation",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "direct_source_parents": parents,
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
