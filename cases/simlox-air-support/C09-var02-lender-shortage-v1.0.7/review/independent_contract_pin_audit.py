"""Independent read-only byte audit for the frozen C09.var02 v1.0.7 contract."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
REPO = AIR.parents[1]
CONTRACT = CASE / "contract.json"
PARENT_INDEX = AIR / "C09-var02-lender-shortage-control-v0.1.1" / "evidence-index.json"
OLD_MANIFEST = AIR / "C09-var02-lender-shortage-v1.0.6" / "prelaunch-manifest.json"
RUN_ID = "c09-var02-v107-shortage-ssh-20261007-01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def walk_pins(node):
    if isinstance(node, dict):
        if all(k in node for k in ("path", "bytes", "sha256")):
            yield node
        for child in node.values():
            yield from walk_pins(child)
    elif isinstance(node, list):
        for child in node:
            yield from walk_pins(child)


def git_bytes(commit: str, path: Path) -> bytes:
    relative = path.relative_to(REPO).as_posix()
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return result.stdout


def main() -> None:
    contract = read(CONTRACT)
    parent = read(PARENT_INDEX)
    old_manifest = read(OLD_MANIFEST)
    failures: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    check(digest(CONTRACT) == "2051fca4baf9555adaab28d870726eee97fe38ac61537630d6b63d2b89a5bb99",
          "frozen contract SHA")
    check(contract["schema"] == "simlox-c09-var02-lender-shortage-v107-child-contract/v1", "schema")
    check(contract["version"] == "1.0.7" and contract["case_id"] == "C09", "identity")
    check(contract["planned_child"]["run_id"] == RUN_ID, "reserved run ID")
    check(not (CASE / "runs" / RUN_ID).exists(), "reserved run absent")
    check(sorted(path.name for path in CASE.iterdir() if path.is_file()) ==
          ["README.md", "contract.json"], "contract-only file scope")

    direct = list(walk_pins(contract))
    for pin in direct:
        path = Path(pin["path"])
        if not path.is_absolute():
            path = (CASE / path).resolve()
        check(path.is_file(), f"direct missing {path}")
        if path.is_file():
            check(path.stat().st_size == pin["bytes"], f"direct size {path}")
            check(digest(path) == pin["sha256"], f"direct SHA {path}")

    records = old_manifest["source_files"]
    check(len(records) == old_manifest["source_count"] == 809, "old manifest count")
    for record in records:
        path = Path(record["path"])
        check(path.is_file(), f"old source missing {record['key']}")
        if path.is_file():
            check(path.stat().st_size == record["bytes"], f"old source size {record['key']}")
            check(digest(path) == record["sha256"], f"old source SHA {record['key']}")

    check(digest(PARENT_INDEX) == contract["published_parent"]["evidence_index"]["sha256"],
          "parent index SHA")
    check(len(parent["source_files"]) == 101 and len(parent["raw_files"]) == 130
          and len(parent["accepted_source_refs"]) == 77, "parent index counts")
    for record in parent["source_files"]:
        path = (PARENT_INDEX.parent / record["path"]).resolve()
        check(path.is_file(), f"parent source missing {path}")
        if path.is_file():
            check(path.stat().st_size == record["bytes"], f"parent source size {path}")
            check(digest(path) == record["sha256"], f"parent source SHA {path}")
            if path.is_relative_to(REPO):
                try:
                    contents = git_bytes(contract["base_commit"], path)
                    check(len(contents) == record["bytes"] and
                          hashlib.sha256(contents).hexdigest() == record["sha256"],
                          f"parent source Git bytes {path}")
                except (OSError, ValueError, subprocess.CalledProcessError):
                    failures.append(f"parent source Git missing {path}")
    for record in parent["accepted_source_refs"]:
        path = (PARENT_INDEX.parent / record["path"]).resolve()
        local = record["local_disk"]
        published = record["published_git"]
        check(path.is_file(), f"accepted source missing {path}")
        if path.is_file():
            check(path.stat().st_size == local["bytes"] and digest(path) == local["sha256"],
                  f"accepted local bytes {path}")
            try:
                contents = git_bytes(contract["base_commit"], path)
                check(len(contents) == published["bytes"] and
                      hashlib.sha256(contents).hexdigest() == published["sha256"],
                      f"accepted Git bytes {path}")
            except (OSError, ValueError, subprocess.CalledProcessError):
                failures.append(f"accepted Git missing {path}")
    for record in parent["raw_files"]:
        path = (PARENT_INDEX.parent / record["path"]).resolve()
        check(path.is_file(), f"accepted raw missing {path}")
        if path.is_file():
            check(path.stat().st_size == record["bytes"] and digest(path) == record["sha256"],
                  f"accepted raw bytes {path}")

    output = {
        "decision": "PASS" if not failures else "FAIL",
        "contract_sha256": digest(CONTRACT),
        "direct_literal_pins_checked": len(direct),
        "excluded_v106_manifest_records_checked": len(records),
        "parent_source_disk_and_git_checked": len(parent["source_files"]),
        "parent_dual_identities_checked": len(parent["accepted_source_refs"]),
        "parent_raw_checked": len(parent["raw_files"]),
        "reserved_run_absent": not (CASE / "runs" / RUN_ID).exists(),
        "failures": failures,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
