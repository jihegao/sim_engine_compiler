"""Seal the accepted J01.var01 local raw run and source files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/j01-var01-determ-probe-20261001-02"
FILES = [
    "README.md", "build.py", "cli-scope-signoff-2026-10-01.md", "contract.json",
    "native-input.json", "parent-diff.json", "run_native_ssh.ps1", "validate.py",
    "make_evidence_index.py", "review/author-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    author = load(HERE / "review/author-validation-2026-10-01.json")
    independent = load(HERE / "review/independent-readonly-2026-10-01.json")
    if closure.get("state") != "native_steps_complete" or closure.get("run_id") != RUN.name:
        raise ValueError("accepted run closure identity differs")
    if invocation.get("run_id") != RUN.name or closure.get("invocation_sha256") != sha(RUN / "invocation.json"):
        raise ValueError("invocation seal differs")
    if len(closure["raw"]) != 11 or len(closure["post_source_sha256"]) != 9:
        raise ValueError("expected raw or source seal count differs")
    for name, record in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    post = closure["post_source_sha256"]
    sources = {
        "native-input.json": HERE / "native-input.json",
        "contract.json": HERE / "contract.json",
        "build.py": HERE / "build.py",
        "validate.py": HERE / "validate.py",
        "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
        "parent-diff.json": HERE / "parent-diff.json",
        "parent-input.json": HERE.parent / "B01-fixed-preparation-v1.0.1/native-input.json",
        "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    }
    for name, path in sources.items():
        if post[name] != sha(path):
            raise ValueError(f"post-run source seal differs: {name}")
    if author.get("passed") is not True or independent.get("passed") is not True or independent.get("verdict") != "GO":
        raise ValueError("review replay is not accepted")
    evidence = {
        "schema": "simlox-j01-var01-determ-evidence-index/v1",
        "case_id": "J01", "variant_id": "J01.var01", "version": "1.0.0",
        "scope": "one fixed-seed B01-derived deterministic 0.5-hour preparation",
        "source_files_sha256": {name: sha(HERE / name) for name in FILES},
        "run": {
            "id": RUN.name, "local_path": str(RUN.resolve()),
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "validation_sha256": sha(RUN / "validation.json"),
            "raw": closure["raw"], "post_source_sha256": post,
        },
        "aborted_preflight_excluded": "-01 SSH preflight created no run directory and launched no native SIMLOX",
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(FILES), "raw_files": len(closure["raw"])}))


if __name__ == "__main__":
    main()
