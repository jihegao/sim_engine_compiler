"""Seal D04.var02 read-only source versions and accepted D04 local raw files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "D04-var02-long-parking-readonly-v1.0.0"
RUN = ROOT / "D04-flight-hour-pm-v1.0.0" / "runs" / "d04-flight-v100-ssh-20260930-01"
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md", "independent-publication-review-2026-10-06.md"}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def main():
    c = load(HERE / "contract.json")
    assert c["version"] == "1.0.1-readonly-candidate"
    old = c["preserved_contract_failure"]
    assert sha(OLD / "contract.json") == old["contract_sha256"]
    assert sha(OLD / "review" / "independent-contract-no-go-2026-10-06.md") == old["independent_no_go_sha256"]
    for p, expected in (
        (ROOT / c["accepted_parent"]["package"] / "native-input.json", c["accepted_parent"]["input_sha256"]),
        (ROOT / c["accepted_parent"]["package"] / "cli-scope-signoff-2026-09-30.md", c["accepted_parent"]["signoff_sha256"]),
        (ROOT / c["instructional_prerequisite"]["package"] / "native-input.json", c["instructional_prerequisite"]["input_sha256"]),
        (ROOT / c["instructional_prerequisite"]["package"] / "cli-scope-signoff-2026-09-30.md", c["instructional_prerequisite"]["signoff_sha256"]),
    ):
        assert sha(p) == expected, p
    author = load(HERE / "review" / "author-readonly-validation-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 349
    assert independent["failures"] == [] and independent["checks_count"] == 7287 and independent["verdict"] == "GO_BOUNDED"
    for name in ("failed-author-validation-2026-10-06.json", "failed-author-validation-v2-2026-10-06.json"):
        assert load(HERE / "review" / name)["passed"] is False
    closure_path, invocation_path = RUN / "closure.json", RUN / "invocation.json"
    assert sha(closure_path) == c["accepted_parent"]["closure_sha256"]
    closure = load(closure_path)
    assert closure["error"] is None and closure["run_id"] == RUN.name
    assert closure["invocation_sha256"] == sha(invocation_path)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, pin in closure["raw"].items():
        p = RUN / name
        assert p.stat().st_size == pin["bytes"] and sha(p) == pin["sha256"], p
    sources = []
    for version in (OLD, HERE):
        for p in sorted(version.rglob("*")):
            if not p.is_file() or p.name in EXCLUDE or p.suffix == ".pyc":
                continue
            if "__pycache__" in p.parts or "runs" in p.relative_to(version).parts:
                continue
            sources.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)})
    assert len(sources) == len({x["path"] for x in sources})
    index = {"schema": "simlox-d04-var02-v101-readonly-evidence-index/v1", "case_id": "D04", "variant_id": "D04.var02",
             "version": "1.0.1", "status": "bounded_readonly_long_parking_ready_for_publication",
             "publication_state": "not_published", "source": sources,
             "accepted_parent": c["accepted_parent"], "instructional_prerequisite": c["instructional_prerequisite"],
             "preserved_contract_failure": old,
             "accepted_run": {"run_id": RUN.name, "local_run_dir": str(RUN.resolve()),
                              "closure": {"bytes": closure_path.stat().st_size, "sha256": sha(closure_path)},
                              "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
                              "raw": closure["raw"]},
             "local_raw_count": 12, "author_checks": author["checks_count"], "independent_verdict": independent,
             "scope": "Read-only mapping of accepted D04: 30-hour no-flight h10-40, 29h ready, 1h mission-reserved, PM only after h41 return.",
             "limits": "One accepted run/seed/aircraft/gap; no direct PM counter trace, other gap lengths, new native run, GUI visual, cross-engine or overall Issue18 claim.",
             "raw_location_policy": "local_only_ignored_accepted_run_not_committed"}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 12, "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
