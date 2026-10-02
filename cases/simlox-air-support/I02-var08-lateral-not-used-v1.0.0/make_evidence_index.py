"""Index I02.var08 restricted source, native and report evidence, and reviews."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2"
SOURCES = (
    ".gitattributes", ".gitignore", "README.md", "contract.json", "native-input.json", "exact-diff.json",
    "build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1", "report_native_ssh.ps1",
    "inspect_native.py", "validate_native.py", "author-validation.json", "make_evidence_index.py",
    "cli-scope-signoff-2026-10-02.md", "review/independent_readonly.py",
    "review/independent-readonly-2026-10-02.json",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(folder, count):
    invocation, closure = read(folder / "invocation.json"), read(folder / "closure.json")
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
    contract, author = read(HERE / "contract.json"), read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-readonly-2026-10-02.json")
    assert contract["direct_parent"]["sha256"] == sha(PARENT / "on-input.json")
    assert contract["source_sha256"] == sha(HERE / "native-input.json")
    assert contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    assert author["passed"] and author["check_count"] == len(author["checks"]) == 32
    assert independent["passed"]
    native = run_index(RUNS / "i02-var08-lateral-out-v100-ssh-20261002-01", 12)
    reports = {station: run_index(RUNS / f"i02-var08-{station}-report-v100-ssh-20261002-01", 2)
               for station in ("base01", "base02", "depot")}
    settings = {station: {"local_path": str((RUNS / "report-settings" / name).resolve()),
                          "sha256": sha(RUNS / "report-settings" / name)}
                for station, name in (("BASE-01", "base-01-item.sxs"), ("BASE-02", "base-02-item.sxs"),
                                      ("DEPOT-01", "depot-item.sxs"))}
    assert settings["BASE-01"]["sha256"] == "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"
    assert settings["BASE-02"]["sha256"] == "83dfecf3d1d88e56d776ecd84268d1a5728cee256b0dd0e5912bf3a5251589c4"
    assert settings["DEPOT-01"]["sha256"] == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"
    parent_native = PARENT / "runs" / "e08-immediate-on-v102-ssh-20261002-01" / "closure.json"
    index = {"schema": "simlox-i02-var08-genuine-lateral-restricted-evidence-index/v1",
             "case_id": "I02", "variant_id": "I02.var08", "version": "1.0.0",
             "scope": "h2 OUT transfer demand does not directly initiate lateral support; later ordinary lateral delivery clears older transfer backorder",
             "raw_publication": "local_sealed_not_committed",
             "source_files_sha256": {name: sha(HERE / name) for name in SOURCES},
             "direct_source_parent": {"package": PARENT.name, "source_sha256": sha(PARENT / "on-input.json"),
                                      "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md"),
                                      "evidence_index_sha256": sha(PARENT / "evidence-index.json"),
                                      "control_native_closure_sha256": sha(parent_native)},
             "native_run": native, "station_reports": reports, "local_report_settings": settings,
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(HERE / "review/independent-readonly-2026-10-02.json")}
    output = HERE / "evidence-index.json"
    encoded = (json.dumps(index, indent=2) + "\n").encode()
    if output.exists():
        assert output.read_bytes() == encoded, "frozen index differs"
    else:
        output.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": sha(output), "sealed_raw_files": 18}))


if __name__ == "__main__":
    main()
