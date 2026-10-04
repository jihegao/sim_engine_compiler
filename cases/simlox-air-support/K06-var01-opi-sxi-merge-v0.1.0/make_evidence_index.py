"""Index the immutable excluded K06 v0.1.0 diagnostic without publishing raw files."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = load(HERE / "contract.json")
run = HERE / "runs" / contract["run_id"]
closure = load(run / "closure.json")
assert closure["run_id"] == contract["run_id"]
assert closure["error"] == "merged.sxo missing or too small"
assert closure["invocation_sha256"] == seal(run / "invocation.json")["sha256"]
assert closure["source_hashes_before"] == closure["source_hashes_after"]
assert len(closure["raw"]) == 11
for name, expected in closure["raw"].items():
    assert seal(run / name) == expected, name
sources = [
    ".gitattributes", ".gitignore", "contract.json", "run_native_ssh.ps1",
    "README.md", "review/diagnostic-verdict-2026-10-05.md", "make_evidence_index.py",
]
result = {
    "schema": "simlox-k06-opi-sxi-merge-diagnostic-evidence-index/v1",
    "case_id": "K06", "variant_id": "K06.var01", "version": "0.1.0",
    "publication_state": "excluded_diagnostic",
    "source": {name: seal(HERE / name) for name in sources},
    "run": {"run_id": contract["run_id"], "local_directory": str(run),
            "invocation": seal(run / "invocation.json"),
            "closure": seal(run / "closure.json"), "raw": closure["raw"]},
    "raw_files_total": len(closure["raw"]),
    "observed_failure": "Duplicate BASE-01 Station across instances; converter error #2013, four-byte SXO, no report.",
    "limits": contract["limits"],
}
destination = HERE / "evidence-index.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"closure_sha256": result["run"]["closure"]["sha256"],
                  "raw_files": len(closure["raw"]), "index_sha256": seal(destination)["sha256"]}))
