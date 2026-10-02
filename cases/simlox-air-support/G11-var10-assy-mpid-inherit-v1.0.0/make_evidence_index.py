"""Index sealed local G11.var10 raw evidence without publishing native files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g11-var10-assy-inherit-v100-ssh-20261003-01"
OUT = HERE / "evidence-index.json"
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py", "contract.json", "exact-diff.json", "native-input-assy-inherit.json", "author-validation.json", "independent_replay.py", "independent-validation.json")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    source = {}
    for name in SOURCE:
        path = HERE / name
        if not path.is_file(): raise FileNotFoundError(path)
        source[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or closure["arm"] != "assy-inherit" or closure["run_id"] != RUN.name: raise ValueError("rejected closure")
    raw = {}
    for name, entry in closure["raw"].items():
        path = RUN / name
        if sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]: raise ValueError(name)
        raw[name] = entry
    document = {"schema": "simlox-g11-var10-assy-mpid-inherit-evidence-index/v1", "case_id": "G11", "variant_id": "G11.var10", "version": "1.0.0", "publication_state": "not_published", "source": source, "manual_sha256": contract["source"]["manual_sha256"], "dictionary_sha256": contract["source"]["dictionary_sha256"], "accepted_parent": contract["accepted_parent"], "run": {"run_id": RUN.name, "local_directory": str(RUN.resolve()), "input_sha256": contract["input"]["sha256"], "invocation_sha256": sha(RUN / "invocation.json"), "closure_sha256": sha(RUN / "closure.json"), "raw": raw}, "scope": "local raw artifacts stay ignored; published hashes identify frozen CLI observations"}
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != data: raise ValueError("frozen evidence index differs")
    else: OUT.write_bytes(data)
    print(json.dumps({"evidence_index_sha256": hashlib.sha256(data).hexdigest(), "raw_records": len(raw)}))

if __name__ == "__main__": main()
