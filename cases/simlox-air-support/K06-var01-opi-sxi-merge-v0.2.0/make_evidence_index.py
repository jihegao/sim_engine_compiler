"""Index K06 v0.2.0 publication sources and ignored native evidence."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = load(HERE / "contract.json")
run = HERE / "runs" / contract["run_id"]
closure = load(run / "closure.json")
assert closure["run_id"] == contract["run_id"] and closure["error"] is None
assert closure["invocation_sha256"] == seal(run / "invocation.json")["sha256"]
assert closure["source_hashes_before"] == closure["source_hashes_after"]
assert len(closure["raw"]) == 17
for name, expected in closure["raw"].items():
    assert seal(run / name) == expected, name
prior = ROOT / "K06-var01-opi-sxi-merge-v0.1.0"
prior_index = load(prior / "evidence-index.json")
assert prior_index["run"]["closure"]["sha256"] == contract["prior_diagnostic"]["closure_sha256"]
sources = [
    ".gitattributes", ".gitignore", "contract.json", "build.py", "source-input.json",
    "run_native_ssh.ps1", "validate.py", "make_evidence_index.py", "README.md",
    "cli-scope-signoff-2026-10-05.md", "review/preflight-2026-10-05.md",
    "review/author-validation-2026-10-05.json", "review/independent_replay.py",
    "review/independent-verdict.json",
]
result = {
    "schema": "simlox-k06-opi-sxi-merge-evidence-index/v1",
    "case_id": "K06", "variant_id": "K06.var01", "version": "0.2.0",
    "publication_state": "not_published",
    "source": {name: seal(HERE / name) for name in sources},
    "run": {"run_id": contract["run_id"], "local_directory": str(run),
            "invocation": seal(run / "invocation.json"),
            "closure": seal(run / "closure.json"), "raw": closure["raw"]},
    "raw_files_total": len(closure["raw"]),
    "prior_diagnostic_index": seal(prior / "evidence-index.json"),
    "parent_closures_sha256": [contract["target"]["closure_sha256"], contract["source"]["closure_sha256"]],
    "manual_sha256": contract["manual"]["sha256"],
    "limits": contract["limits"],
}
destination = HERE / "evidence-index.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"closure_sha256": result["run"]["closure"]["sha256"],
                  "raw_files": len(closure["raw"]), "index_sha256": seal(destination)["sha256"]}))
