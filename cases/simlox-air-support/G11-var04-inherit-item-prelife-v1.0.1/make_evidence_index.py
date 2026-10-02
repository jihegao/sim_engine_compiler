"""Index sealed local G11.var04 raw evidence without publishing native files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {arm: f"g11-var04-{arm}-v101-ssh-20261002-01" for arm in ("explicit-control", "inherited")}
OUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    source = {}
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
                 "validate_native.py", "contract.json", "exact-diff.json",
                 "native-input-explicit-control.json", "native-input-inherited.json",
                 "author-validation.json", "independent_replay.py", "independent-verdict.json"):
        path = HERE / name
        if not path.is_file():
            raise FileNotFoundError(path)
        source[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    runs = {}
    for arm, run_id in RUNS.items():
        folder = HERE / "runs" / run_id
        closure = json.loads((folder / "closure.json").read_text(encoding="utf-8-sig"))
        if closure["error"] is not None or closure["arm"] != arm or closure["run_id"] != run_id:
            raise ValueError(f"rejected closure {run_id}")
        raw = {}
        for name, entry in closure["raw"].items():
            path = folder / name
            if sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
                raise ValueError(f"raw seal mismatch {run_id}/{name}")
            raw[name] = entry
        runs[arm] = {"run_id": run_id, "local_directory": str(folder.resolve()),
                     "input_sha256": contract["inputs"][arm]["sha256"],
                     "invocation_sha256": sha(folder / "invocation.json"),
                     "closure_sha256": sha(folder / "closure.json"), "raw": raw}
    doc = {"schema": "simlox-g11-var04-inherit-item-prelife-evidence-index/v1", "case_id": "G11",
           "variant_id": "G11.var04", "version": "1.0.1", "publication_state": "not_published",
           "source": source, "manual_sha256": contract["source"]["manual_sha256"],
           "dictionary_sha256": contract["source"]["dictionary_sha256"],
           "accepted_parent": contract["accepted_parent"],
           "accepted_prelife_schema_donor": contract["accepted_prelife_schema_donor"],
           "excluded_previous_candidate": dict(contract["excluded_previous_candidate"],
               closure_sha256="520cef00eaa7e807f23ed29e1232587fa465ff458356415030705c59fe336e06"),
           "runs": runs,
           "scope": "local raw artifacts stay ignored; published hashes identify frozen CLI observations"}
    encoded = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != encoded:
            raise ValueError("frozen evidence index differs")
    else:
        OUT.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": hashlib.sha256(encoded).hexdigest(),
                      "raw_records": sum(len(x["raw"]) for x in runs.values())}))


if __name__ == "__main__":
    main()
