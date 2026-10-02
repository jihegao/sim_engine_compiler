"""Index frozen E08.var03 Y/N sources, eight guarded closures and reviews."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2"
ARMS = ("off", "on")
STATIONS = (("base-01", "base01"), ("base-02", "base02"), ("depot", "depot"))
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "build.py", "describe_diff.py",
    "off-input.json", "on-input.json", "exact-diff.json", "check_roundtrip.py",
    "run_native_ssh.ps1", "report_native_ssh.ps1", "validate_native.py", "author-validation.json",
    "cli-scope-signoff-2026-10-02.md", "make_evidence_index.py", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-02.json",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder, expected):
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


def main():
    contract, author = read(HERE / "contract.json"), read(HERE / "author-validation.json")
    reviewer = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert author["passed"] and author["check_count"] == len(author["checks"]) == 71
    assert reviewer["passed"]
    assert contract["direct_parent"]["source_sha256"] == sha(PARENT / "on-input.json")
    donor = HERE.parent / contract["transfer_schema_donor"]["package"]
    assert contract["transfer_schema_donor"]["source_sha256"] == sha(donor / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    native, reports = {}, {}
    for arm in ARMS:
        assert contract[f"{arm}_input_sha256"] == sha(HERE / f"{arm}-input.json")
        native[arm] = run_index(RUNS / f"e08-dlayl-{arm}-v100-ssh-20261002-01", 12)
        reports[arm] = {}
        for station, _ in STATIONS:
            item = run_index(RUNS / f"e08-dlayl-{arm}-{station}-report-v100-ssh-20261002-01", 2)
            invocation = read(Path(item["local_path"]) / "invocation.json")
            assert invocation["source_closure_sha256"] == native[arm]["closure_sha256"]
            reports[arm][station] = item
    selectors = {station: {"local_path": str((RUNS / "report-settings" / f"{station}-item.sxs").resolve()),
                           "sha256": sha(RUNS / "report-settings" / f"{station}-item.sxs")}
                 for station, _ in STATIONS}
    assert {s: d["sha256"] for s, d in selectors.items()} == {
        "base-01": "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b",
        "base-02": "83dfecf3d1d88e56d776ecd84268d1a5728cee256b0dd0e5912bf3a5251589c4",
        "depot": "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"}
    index = {"schema": "simlox-e08-var03-delayed-lateral-evidence-index/v1", "case_id": "E08", "variant_id": "E08.var03",
             "version": "1.0.0", "scope": "bounded no observed DLAYL Y/N effect when peer's future item comes from scheduled BETWEEN transfer",
             "raw_publication": "local_sealed_not_committed",
             "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
             "direct_source_parent": {"package": PARENT.name, "source_sha256": sha(PARENT / "on-input.json"),
                                      "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md"),
                                      "evidence_index_sha256": sha(PARENT / "evidence-index.json"),
                                      "on_native_closure_sha256": sha(PARENT / "runs/e08-immediate-on-v102-ssh-20261002-01/closure.json"),
                                      "off_native_closure_sha256": sha(PARENT / "runs/e08-immediate-off-v102-ssh-20261002-01/closure.json")},
             "transfer_schema_donor": {"package": donor.name, "source_sha256": sha(donor / "native-input.json"),
                                       "publication_signoff_sha256": sha(donor / "cli-scope-signoff-2026-10-02.md"),
                                       "evidence_index_sha256": sha(donor / "evidence-index.json")},
             "native_runs": native, "station_reports": reports, "local_report_settings": selectors,
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json")}
    output = HERE / "evidence-index.json"
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == encoded, "frozen evidence index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 36}))


if __name__ == "__main__":
    main()
