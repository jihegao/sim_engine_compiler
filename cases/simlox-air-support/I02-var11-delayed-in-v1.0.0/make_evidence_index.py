"""Index frozen I02.var11 source, parent control and sealed local native files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2"
RUNS = HERE / "runs"
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "build.py",
    "describe_diff.py", "native-input.json", "exact-diff.json", "check_roundtrip.py",
    "run_native_ssh.ps1", "make_report_settings.py", "report_native_ssh.ps1",
    "validate_native.py", "author-validation.json", "cli-scope-signoff-2026-10-02.md",
    "make_evidence_index.py", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-02.json",
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
    assert author["passed"] and author["check_count"] == len(author["checks"]) == 41
    assert reviewer["passed"]
    assert contract["source_sha256"] == sha(HERE / "native-input.json")
    assert contract["direct_parent"]["source_sha256"] == sha(PARENT / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    native = run_index(RUNS / "i02-var11-in-delay2-v100-ssh-20261002-01", 12)
    report = run_index(RUNS / "i02-var11-depot-item-v100-ssh-20261002-01", 2)
    report_invocation = read(Path(report["local_path"]) / "invocation.json")
    assert report_invocation["source_closure_sha256"] == native["closure_sha256"]
    assert report_invocation["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
    selector = RUNS / "report-settings/item-position-results.sxs"
    assert sha(selector) == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"
    index = {
        "schema": "simlox-i02-var11-delayed-in-evidence-index/v1",
        "case_id": "I02", "variant_id": "I02.var11", "version": "1.0.0",
        "scope": "bounded tracked one-unit scheduled IN TFDT0 versus TFDT2",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
        "direct_source_parent": {
            "package": PARENT.name, "source_sha256": sha(PARENT / "native-input.json"),
            "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md"),
            "evidence_index_sha256": sha(PARENT / "evidence-index.json"),
            "native_closure_sha256": sha(PARENT / "runs/i02-var01-in-v102-ssh-20261002-01/closure.json"),
            "item_report_closure_sha256": sha(PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01/closure.json"),
        },
        "native_run": native, "depot_item_report": report,
        "local_report_settings": {"local_path": str(selector.resolve()), "sha256": sha(selector)},
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json"),
        "sealed_raw_file_count": 14,
    }
    output = HERE / "evidence-index.json"
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == encoded, "frozen evidence index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 14}))


if __name__ == "__main__":
    main()
