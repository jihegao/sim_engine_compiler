"""Read-only verification of every frozen accepted source, run and installed byte pin."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "contract.json"


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def pinned(path: Path, expected: dict) -> None:
    actual = digest(path.read_bytes())
    size = expected.get("bytes", expected.get("size_bytes"))
    assert actual == {"bytes": size, "sha256": expected["sha256"]}, (str(path), actual, expected)


def resolved(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (HERE / p).resolve()


def published(path: Path, commit: str) -> bytes:
    relative = path.relative_to(REPO).as_posix()
    return subprocess.check_output(["git", "-C", str(REPO), "show", f"{commit}:{relative}"])


def visit_source(node: object, commit: str, counts: dict) -> None:
    if isinstance(node, dict):
        if {"path", "local_disk", "published_git"} <= set(node):
            p = resolved(node["path"])
            pinned(p, node["local_disk"])
            assert digest(published(p, commit)) == node["published_git"], ("published Git", str(p))
            counts["source_disk_git_pairs"] += 1
            return
        for value in node.values():
            visit_source(value, commit, counts)
    elif isinstance(node, list):
        for value in node:
            visit_source(value, commit, counts)


def visit_runs(node: object, counts: dict) -> None:
    if isinstance(node, dict):
        if {"path", "raw", "closure", "invocation"} <= set(node) and isinstance(node["raw"], (dict, list)):
            run = resolved(node["path"])
            closure = node["closure"]
            invocation = node["invocation"]
            pinned(resolved(closure["path"]) if "path" in closure else run / "closure.json", closure)
            pinned(resolved(invocation["path"]) if "path" in invocation else run / "invocation.json", invocation)
            counts["closures"] += 1
            counts["invocations"] += 1
            assert len(node["raw"]) == node.get("raw_count", len(node["raw"]))
            records = node["raw"].items() if isinstance(node["raw"], dict) else enumerate(node["raw"])
            for name, meta in records:
                pinned(resolved(meta["path"]) if "path" in meta else run / name, meta)
                counts["raw"] += 1
            return
        for value in node.values():
            visit_runs(value, counts)
    elif isinstance(node, list):
        for value in node:
            visit_runs(value, counts)


def verify() -> dict:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["schema"] == "simlox-c09-var02-lender-shortage-v101-contract/v1"
    commit = c["base_commit"]
    counts = {"source_disk_git_pairs": 0, "closures": 0, "invocations": 0, "raw": 0,
              "installed": 0, "excluded_v100": 0}
    visit_source(c, commit, counts)
    visit_runs(c, counts)
    for value in c["installed"].values():
        pinned(resolved(value["path"]), value)
        counts["installed"] += 1
    for value in c["excluded_v100"]["records"].values():
        pinned(resolved(value["path"]), value)
        counts["excluded_v100"] += 1
    assert counts["raw"] == 117 and counts["closures"] == counts["invocations"] == 9, counts
    assert counts["installed"] == 3 and counts["excluded_v100"] == 2, counts
    return {"schema": "c09-var02-v101-source-verification/v1", "passed": True,
            "contract_sha256": digest(CONTRACT.read_bytes())["sha256"], "base_commit": commit,
            "counts": counts}


if __name__ == "__main__":
    try:
        result = verify()
    except Exception as exc:
        result = {"schema": "c09-var02-v101-source-verification/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.exit(0 if result["passed"] else 1)
