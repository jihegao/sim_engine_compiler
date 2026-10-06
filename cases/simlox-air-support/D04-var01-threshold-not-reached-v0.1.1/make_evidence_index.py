"""Seal both D04.var01 source versions and the accepted/child local raw evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V010 = ROOT / "D04-var01-threshold-not-reached-v0.1.0"
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0" / "runs" / "d04-flight-v100-ssh-20260930-01"
CHILD = HERE / "runs" / "d04-var01-op4-v011-ssh-20261006-01"
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md", "independent-publication-review-2026-10-06.md"}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def seal(role, folder, expected):
    closure_path = folder / "closure.json"
    invocation_path = folder / "invocation.json"
    assert sha(closure_path) == expected, closure_path
    c = load(closure_path)
    assert c["error"] is None and c["run_id"] == folder.name
    assert c["invocation_sha256"] == sha(invocation_path)
    assert c["source_hashes_before"] == c["source_hashes_after"]
    assert len(c["raw"]) == 12
    for name, pin in c["raw"].items():
        p = folder / name
        assert p.stat().st_size == pin["bytes"] and sha(p) == pin["sha256"], p
    return {"role": role, "run_id": folder.name, "local_run_dir": str(folder.resolve()),
            "closure": {"bytes": closure_path.stat().st_size, "sha256": expected},
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "raw": c["raw"]}

def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.1-contract-candidate"
    failed = contract["preserved_prelaunch_failure"]
    assert sha(V010 / "contract.json") == failed["contract_sha256"]
    assert sha(V010 / "review" / "independent-contract-go-2026-10-06.md") == failed["independent_contract_go_sha256"]
    assert sha(V010 / "review" / "independent-prelaunch-no-go-2026-10-06.md") == failed["independent_prelaunch_no_go_sha256"]
    assert not (V010 / "runs").exists()
    for path, expected in [
        (ROOT / contract["accepted_parent"]["package"] / "native-input.json", contract["accepted_parent"]["input_sha256"]),
        (ROOT / contract["accepted_parent"]["package"] / "cli-scope-signoff-2026-09-30.md", contract["accepted_parent"]["signoff_sha256"]),
        (ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json", contract["instructional_prerequisites"][0]["input_sha256"]),
        (ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md", contract["instructional_prerequisites"][0]["signoff_sha256"]),
    ]:
        assert sha(path) == expected, path
    assert sha(HERE / "native-input.json") == "cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd"
    author = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 7084
    assert independent["verdict"] == "GO_BOUNDED" and independent["passed"] is True and independent["checks_count"] == 8195
    sources = []
    for version in (V010, HERE):
        for p in sorted(version.rglob("*")):
            if not p.is_file() or p.name in EXCLUDE or p.suffix == ".pyc":
                continue
            if "runs" in p.relative_to(version).parts or "__pycache__" in p.parts:
                continue
            sources.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)})
    assert len(sources) == len({x["path"] for x in sources})
    runs = [seal("accepted_parent", PARENT, contract["accepted_parent"]["closure_sha256"]),
            seal("bounded_child", CHILD, "98d30d678431fb8ce6661b2cac2b5a3681b226bca32a8076c7eac8899e18dea0")]
    index = {"schema": "simlox-d04-var01-v011-evidence-index/v1", "case_id": "D04", "variant_id": "D04.var01",
             "version": "0.1.1", "status": "bounded_at_vs_below_threshold_ready_for_publication",
             "publication_state": "not_published", "source": sources,
             "accepted_parent": contract["accepted_parent"], "instructional_prerequisites": contract["instructional_prerequisites"],
             "preserved_prelaunch_failure": failed, "runs": runs, "local_raw_count": 24,
             "author_checks": author["checks_count"], "independent_verdict": independent,
             "scope": "One OPHOURS=3 parent versus OPHOURS=4 child with three scheduled mission-hours and no child PM through h60.",
             "limits": "One arm of before/at/over panel; v0.1.0 NO_GO prelaunch excluded; no general threshold, GUI visual, cross-engine or overall Issue18 claim.",
             "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 24, "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
