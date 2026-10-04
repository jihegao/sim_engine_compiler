"""Seal the K09.var03 source-bound dossier without modifying native raw files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "K09-var01-report-settings-v1.0.1"
contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))


def seal(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


linked = {
    "K09_var01_index": (PARENT / "evidence-index.json", "evidence_index_sha256"),
    "K09_var01_contract": (PARENT / "contract.json", "contract_sha256"),
    "K09_var01_independent": (PARENT / "review/independent-verdict.json", "independent_verdict_sha256"),
    "K09_var01_signoff": (PARENT / "cli-scope-signoff-2026-10-05.md", "signoff_sha256"),
}
for name, (path, key) in linked.items():
    assert seal(path)["sha256"] == contract["parent"][key], name
index = json.loads((PARENT / "evidence-index.json").read_text(encoding="utf-8"))
accepted = index["runs"]["bounded_candidate"]
assert accepted["run_id"] == contract["parent"]["run_id"]
run = PARENT / "runs" / accepted["run_id"]
assert seal(run / "closure.json") == accepted["closure"]
assert seal(run / "invocation.json") == accepted["invocation"]
assert len(accepted["raw"]) == 8
for name, expected in accepted["raw"].items():
    assert seal(run / name) == expected, name
sources = [
    ".gitattributes", "contract.json", "README.md", "validate.py", "make_evidence_index.py",
    "cli-scope-signoff-2026-10-05.md", "review/preflight-2026-10-05.md",
    "review/author-validation-2026-10-05.json", "review/independent_replay.py",
    "review/independent-verdict.json",
]
result = {
    "schema": "simlox-k09-var03-report-json-evidence-index/v1",
    "case_id": "K09", "variant_id": "K09.var03", "version": "1.0.0",
    "publication_state": "not_published",
    "evidence_mode": "source-bound reuse; no new native invocation or raw copy",
    "source": {name: seal(HERE / name) for name in sources},
    "linked_sources": {name: seal(path) for name, (path, _) in linked.items()},
    "reused_accepted_run": {"run_id": accepted["run_id"], "invocation": accepted["invocation"],
                            "closure": accepted["closure"], "raw": accepted["raw"]},
    "reused_raw_seals": 8,
    "limits": contract["limits"],
}
destination = HERE / "evidence-index.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"raw_seals": 8, "index_sha256": seal(destination)["sha256"]}))
