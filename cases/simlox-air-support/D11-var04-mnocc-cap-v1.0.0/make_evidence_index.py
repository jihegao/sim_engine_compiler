"""Index the three frozen MNOCC sources, reviews, and sealed native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_SHAS = {
    0: "d6bacab5d9ccf99154eb95d7c2b324493bfdc6eca8576d0b76d2cf95a2dee9a3",
    1: "548e89ae0e7fede7f604bd7d886a9219b70122530f92fb9a1baa34c6eb3bdd73",
    2: "fb0c75f5bf08ba560cb12a2a9ac7bcb91edf1dc01e983d0e47020cdc92c3c7fc",
}
FILES = [
    ".gitattributes", ".gitignore", "README.md", "build.py", "check_roundtrip.py",
    "cli-scope-signoff-2026-10-01.md", "contract.json", "describe_diff.py",
    "exact-diff.json", "make_evidence_index.py", "run_native_ssh.ps1", "validate_native.py",
    "review/independent_readonly.py", "review/static-review-2026-10-01.md",
]
FILES += [f"native-mnocc-{limit}.json" for limit in INPUT_SHAS]
for limit in INPUT_SHAS:
    FILES += [f"review/author-validation-mnocc-{limit}-2026-10-01.json",
              f"review/independent-readonly-mnocc-{limit}-2026-10-01.json"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    runs = {}
    for limit, input_sha in INPUT_SHAS.items():
        run = HERE / "runs" / f"d11-mnocc-{limit}-v100-ssh-20261001-01"
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        author = json.loads((HERE / f"review/author-validation-mnocc-{limit}-2026-10-01.json").read_text())
        independent = json.loads((HERE / f"review/independent-readonly-mnocc-{limit}-2026-10-01.json").read_text())
        if closure.get("error") is not None or closure["run_id"] != run.name:
            raise ValueError(f"native closure invalid for MNOCC={limit}")
        if invocation["input_sha256"] != input_sha or closure["source_hashes_before"]["input"] != input_sha:
            raise ValueError(f"source pin differs for MNOCC={limit}")
        if closure["source_hashes_after"] != closure["source_hashes_before"]:
            raise ValueError(f"source changed during MNOCC={limit} run")
        if closure["invocation_sha256"] != sha(run / "invocation.json"):
            raise ValueError(f"invocation seal differs for MNOCC={limit}")
        if len(closure["raw"]) != 12:
            raise ValueError(f"raw artifact count differs for MNOCC={limit}")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"raw seal differs for MNOCC={limit}: {name}")
        if not author["passed"] or not independent["passed"] or independent["verdict"] != "GO":
            raise ValueError(f"review failed for MNOCC={limit}")
        runs[str(limit)] = {
            "run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": input_sha,
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "sxo_sha256": sha(run / "model.sxo"),
            "raw": closure["raw"],
            "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
        }
    index = {
        "schema": "simlox-d11-mnocc-cap-v100-evidence-index/v1",
        "case_id": "D11", "variant_id": "D11.var04", "version": "1.0.0",
        "scope": "direct MNOCC 0/1/2 cap on one unlinked system PM",
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(FILES), "native_runs": len(runs), "raw_files": sum(len(r["raw"]) for r in runs.values())}))


if __name__ == "__main__":
    main()
