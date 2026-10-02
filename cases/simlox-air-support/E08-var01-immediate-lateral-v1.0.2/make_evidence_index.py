"""Index immutable E08 source, eight local native/report runs, and reviews."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PARENT = HERE.parent / "E07-item-specific-transport-v1.0.1"
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "on-input.json", "off-input.json",
    "exact-diff.json", "build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
    "report_native_ssh.ps1", "validate_native.py", "inspect_native.py", "make_evidence_index.py",
    "author-validation.json", "cli-scope-signoff-2026-10-02.md", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-02.json",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder, count):
    invocation = read(folder / "invocation.json")
    closure = read(folder / "closure.json")
    assert closure["error"] is None and closure["run_id"] == folder.name
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"]
    assert len(closure["raw"]) == count
    for name, seal in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": folder.name, "local_path": str(folder.resolve()),
            "invocation_sha256": sha(folder / "invocation.json"), "closure_sha256": sha(folder / "closure.json"),
            "raw": closure["raw"]}


def main():
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert contract["parent_sha256"] == sha(PARENT / "native-input.json")
    assert contract["on_input_sha256"] == sha(HERE / "on-input.json")
    assert contract["off_input_sha256"] == sha(HERE / "off-input.json")
    assert author["passed"] and author["check_count"] == len(author["checks"]) == 79
    assert independent["passed"]
    native = {variant: run_index(RUNS / f"e08-immediate-{variant}-v102-ssh-20261002-01", 12)
              for variant in ("on", "off")}
    reports = {variant: {station: run_index(RUNS / f"e08-{variant}-{station}-report-v102-ssh-20261002-01", 2)
                         for station in ("base01", "base02", "depot")}
               for variant in ("on", "off")}
    settings = {station: {"local_path": str((RUNS / "report-settings" / name).resolve()),
                          "sha256": sha(RUNS / "report-settings" / name)}
                for station, name in (("BASE-01", "base-01-item.sxs"), ("BASE-02", "base-02-item.sxs"),
                                      ("DEPOT-01", "depot-item.sxs"))}
    assert settings["BASE-01"]["sha256"] == "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"
    assert settings["BASE-02"]["sha256"] == "83dfecf3d1d88e56d776ecd84268d1a5728cee256b0dd0e5912bf3a5251589c4"
    assert settings["DEPOT-01"]["sha256"] == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"
    index = {"schema": "simlox-e08-var01-immediate-lateral-v102-evidence-index/v1",
             "case_id": "E08", "variant_id": "E08.var01", "version": "1.0.2",
             "scope": "one IMMEDIATE DLAYL=N lateral peer versus ordinary depot ENLAT Y/N matched control",
             "raw_publication": "local_sealed_not_committed",
             "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
             "direct_source_parent": {"package": PARENT.name, "source_sha256": sha(PARENT / "native-input.json"),
                                      "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-01.md")},
             "native_runs": native, "station_reports": reports, "local_report_settings": settings,
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json")}
    output = HERE / "evidence-index.json"
    raw = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == raw, "frozen evidence index differs"
    else:
        output.write_bytes(raw)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 36}))


if __name__ == "__main__":
    main()
