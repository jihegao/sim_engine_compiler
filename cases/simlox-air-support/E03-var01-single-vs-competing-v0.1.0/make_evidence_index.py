"""Seal E03.var01 source bytes and the accepted parent/child local raw runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "evidence-index.json"
RUNS = (
    ("parent", ROOT / "E03-two-aircraft-shared-spare-v1.0.0" / "runs" / "e03-v100-ssh-20260929-01", "b200b18fbbed80dcc7ff9e9f4e2e1d7952734449b49a400a509d054090a9b7d6"),
    ("child", HERE / "runs" / "e03-var01-single-v010-ssh-20261006-01", "0c12233574445246d8732f3f1d4202fce3e091a39cef5118a6a5a9ca6ac08690"),
)
PREREQUISITES = (
    ("E03", ROOT / "E03-two-aircraft-shared-spare-v1.0.0" / "cli-scope-signoff-2026-09-29.md", "dedf59901c805c7bbfd6c7421f02d0b051d0fbbc38c97819970988203e47c4e1"),
    ("E02", ROOT / "E02-zero-stock-local-backorder-v1.0.0" / "cli-scope-signoff-2026-09-29.md", "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6"),
    ("A03", ROOT / "A03-two-aircraft-formation-v1.0.1" / "cli-scope-signoff-2026-09-29.md", "6c8d3998f20e216d0403b807866fcbe306f68ebc6f376693334435e808747b2b"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path in (OUTPUT, HERE / "cli-scope-signoff-2026-10-06.md") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    prereqs = []
    for case_id, path, expected in PREREQUISITES:
        assert sha(path) == expected
        prereqs.append({"case_id": case_id, "signoff_path": str(path.resolve()), "signoff_bytes": path.stat().st_size, "signoff_sha256": expected})
    runs = []
    for role, run, expected in RUNS:
        closure_path, invocation_path = run / "closure.json", run / "invocation.json"
        assert sha(closure_path) == expected
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run.name and closure["invocation_sha256"] == sha(invocation_path) and closure["error"] is None
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert len(closure["raw"]) == 12
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        runs.append({"role": role, "run_id": run.name, "local_run_dir": str(run.resolve()), "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)}, "closure": {"bytes": closure_path.stat().st_size, "sha256": expected}, "raw": closure["raw"]})
    original = json.loads((HERE / "review" / "author-replay-v010-failed.json").read_text(encoding="utf-8-sig"))
    corrected = json.loads((HERE / "review" / "author-replay-v011.json").read_text(encoding="utf-8-sig"))
    independent = json.loads((HERE / "review" / "independent-verdict.json").read_text(encoding="utf-8-sig"))
    ledger = json.loads((HERE / "review" / "author-ledger-reconciliation.json").read_text(encoding="utf-8-sig"))
    assert original["passed"] is False and original["differences"] == ["terminal aircraft ready"] and original["checks"] == 64
    assert corrected["passed"] is True and corrected["checks"] == 64 and corrected["frozen_prelaunch_validator_sha256"] == sha(HERE / "validate_native_cli.py")
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks"] == independent["passed_checks"] == 803
    assert ledger["passed"] is True and ledger["checks"] == 579
    index = {"schema": "simlox-e03-var01-v010-evidence-index/v1", "case_id": "E03", "variant_id": "E03.var01", "version": "0.1.0", "status": "native_behavior_accepted_cli_scope_ready_for_publication", "publication_state": "not_published", "source": source, "prerequisites": prereqs, "accepted_runs": runs, "accepted_raw_count": 24, "author_original_result": "failed_63_of_64_preserved", "author_corrected_checks": 64, "author_ledger_checks": 579, "independent_checks": 803, "scope": "one seeded mission, one observed physical LRU replacement demand served by the opening local spare, no backorder", "limits": "Exposure and stochastic draws differ from the two-mission parent; no FIFO, priority, simultaneous-demand, general allocation, GUI visual or cross-engine claim; K01/K08 captures and excluded I07 opening-three/E05.var02 diagnostics remain outside scope", "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": 24, "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
