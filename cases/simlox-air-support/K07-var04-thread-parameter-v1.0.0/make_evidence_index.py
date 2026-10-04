"""Seal the K07.var04 cross-reference and verify reused J04 native evidence."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = read(HERE / "contract.json")
linked = {
    "K02": ROOT / "K02-var01-json-structure-v1.0.1/evidence-index.json",
    "K07_cli": ROOT / "K07-var02-cli-evidence-v1.0.0/evidence-index.json",
    "J04_thread_one": ROOT / "J04-var03-nreps-cap-v1.0.0/evidence-index.json",
    "J04_thread_two": ROOT / "J04-var04-thread-repro-v1.0.0/evidence-index.json",
    "J04_contract": ROOT / "J04-var04-thread-repro-v1.0.0/contract.json",
    "J04_independent": ROOT / "J04-var04-thread-repro-v1.0.0/review/independent-readonly-2026-10-01.json",
}
expected = [
    contract["instructional_prerequisite"]["K02_index_sha256"],
    contract["instructional_prerequisite"]["K07_cli_workflow_index_sha256"],
    contract["tested_model"]["parent_index_sha256"],
    contract["tested_model"]["thread_study_index_sha256"],
    contract["tested_model"]["thread_study_contract_sha256"],
    contract["tested_model"]["thread_study_independent_verdict_sha256"],
]
assert [seal(path)["sha256"] for path in linked.values()] == expected
reused = []
for threads, package_name in ((1, "J04-var03-nreps-cap-v1.0.0"), (2, "J04-var04-thread-repro-v1.0.0")):
    package = ROOT / package_name
    index = read(package / "evidence-index.json")
    assert len(index["accepted_runs"]) == 2
    for item in index["accepted_runs"]:
        run = package / "runs" / item["run_id"]
        assert seal(run / "closure.json")["sha256"] == item["closure_sha256"]
        assert len(item["raw"]) == 11
        for name, raw_seal in item["raw"].items():
            assert seal(run / name) == raw_seal
        reused.append({"run_id": item["run_id"], "threads": threads,
                       "closure": seal(run / "closure.json"),
                       "raw": item["raw"]})
assert len(reused) == 4
sources = [
    ".gitattributes", "contract.json", "README.md", "validate.py", "make_evidence_index.py",
    "cli-scope-signoff-2026-10-05.md", "review/preflight-2026-10-05.md",
    "review/author-validation-2026-10-05.json", "review/independent_replay.py",
    "review/independent-verdict.json",
]
result = {
    "schema": "simlox-k07-var04-thread-reference-evidence-index/v1",
    "case_id": "K07", "variant_id": "K07.var04", "version": "1.0.0",
    "publication_state": "not_published",
    "evidence_mode": "source-bound reuse; no new native invocation or raw copy",
    "source": {name: seal(HERE / name) for name in sources},
    "linked_sources": {name: seal(path) for name, path in linked.items()},
    "reused_accepted_runs": reused,
    "reused_raw_seals": 44,
    "limits": contract["limits"],
}
destination = HERE / "evidence-index.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"reused_runs": len(reused), "raw_seals": 44,
                  "index_sha256": seal(destination)["sha256"]}))
