"""Read-only exact accepted-source, Git, installed-byte and raw seal verifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASES = HERE.parent
REPO = HERE.parents[2]
CONTRACT_SHA = "e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12"
RUN_ID = "c02-var01-v101-personnel0-ssh-20261007-01"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(path: Path, spec: dict) -> None:
    data = path.read_bytes()
    assert len(data) == spec["bytes"] and digest(data) == spec["sha256"], str(path)


def git_bytes(base: str, path: str) -> bytes:
    result = subprocess.run(["git", "show", f"{base}:{path}"], cwd=REPO,
                            capture_output=True, check=True)
    return result.stdout


def verify() -> dict:
    check(HERE / "contract.json", {"bytes": 48041, "sha256": CONTRACT_SHA})
    c = json.loads((HERE / "contract.json").read_bytes())
    assert c["ownership"]["base_commit"] == "1a80bbe5bcfb0351f27c55c7e0cf665bc761e4c6"
    base = c["ownership"]["base_commit"]
    counts = {"published_source": 0, "accepted_raw": 0, "context": 0}
    for label, package in (("classification", c["accepted_evidence"]["classification"]),
                           ("C02_parent", c["accepted_evidence"]["C02_parent"])):
        if label == "classification":
            for spec in package["source_files"]:
                path = f"cases/simlox-air-support/{package['package']}/{spec['path']}"
                check(REPO / path, spec)
                data = git_bytes(base, path)
                assert len(data) == spec["bytes"] and digest(data) == spec["sha256"], path
                counts["published_source"] += 1
        else:
            for spec in package["source_files_dual_local_and_git"]:
                path = f"cases/simlox-air-support/{package['package']}/{spec['path']}"
                check(REPO / path, spec["local_disk"])
                data = git_bytes(base, path)
                git_spec = spec["published_git"]
                assert len(data) == git_spec["bytes"] and digest(data) == git_spec["sha256"], path
                counts["published_source"] += 1
            for accepted in package["accepted_runs"]:
                root = Path(accepted["local_run_dir"])
                check(root / "closure.json", accepted["closure"])
                check(root / "invocation.json", accepted["invocation"])
                closure = json.loads((root / "closure.json").read_text(encoding="utf-8-sig"))
                assert closure["run_id"] == accepted["run_id"]
                assert closure["invocation_sha256"] == accepted["invocation"]["sha256"]
                assert closure["raw"] == accepted["raw"]
                for name, spec in accepted["raw"].items():
                    check(root / name, spec)
                    counts["accepted_raw"] += 1
    c01 = c["accepted_evidence"]["C01_capacity_zero_context"]
    for name, spec in c01["source_files_dual_local_and_git"].items():
        path = f"cases/simlox-air-support/{c01['package']}/{name}"
        check(REPO / path, {"bytes": spec["local_bytes"], "sha256": spec["local_sha256"]})
        data = git_bytes(base, path)
        assert len(data) == spec["published_git_bytes"] and digest(data) == spec["published_git_sha256"], path
        counts["published_source"] += 1
    root = Path(c01["local_run_dir"])
    for name in ("closure", "invocation"):
        check(root / c01[name]["path"], c01[name])
    closure = json.loads((root / c01["closure"]["path"]).read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == c01["run_id"]
    assert closure["invocation_sha256"] == c01["invocation"]["sha256"]
    assert closure["raw"] == c01["raw"]
    for name, spec in c01["raw"].items():
        check(root / name, spec)
        counts["accepted_raw"] += 1
    for spec in c["excluded_v100"]["files"]:
        check(CASES / spec["path"], spec)
        counts["context"] += 1
    for name in ("exe", "manual", "dictionary"):
        check(Path(c["installed"][name]["path"]), c["installed"][name])
        counts["context"] += 1
    for name in ("source", "execution_plan", "publication_index_at_selection"):
        path = REPO / c["catalog"][name]["path"]
        if name == "publication_index_at_selection" and "--sealed" in sys.argv:
            path = HERE / "preserved-context" / "publication-index-at-selection.json"
        check(path, c["catalog"][name])
        counts["context"] += 1
    selection = REPO / c["ownership"]["historical_v100_selection_context"]["path"]
    if "--sealed" in sys.argv:
        selection = HERE / "preserved-context" / "c02-var01-owner-selection-20261007.json"
    check(selection,
          c["ownership"]["historical_v100_selection_context"])
    counts["context"] += 1
    assert counts["published_source"] == 47 and counts["accepted_raw"] == 55, counts
    assert (HERE / "runs" / RUN_ID).exists() is False or "--sealed" in sys.argv
    return {"schema": "c02-var01-v101-source-verification/v1", "passed": True,
            "base_commit": base, "counts": counts}


if __name__ == "__main__":
    try:
        result = verify()
    except Exception as exc:
        result = {"schema": "c02-var01-v101-source-verification/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0 if result["passed"] else 1)
