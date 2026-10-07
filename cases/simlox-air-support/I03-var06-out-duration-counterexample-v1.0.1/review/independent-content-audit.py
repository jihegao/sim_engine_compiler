"""Read-only independent audit of the frozen I03.var06 v1.0.1 evidence index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
INDEX = HERE / "evidence-index.json"
INDEX_SHA = "b4e82d39d5780e3eb981a717a0c9b598489c62747e9acc1e5ab5bfeae4e9ffbb"
BASE = "3887a7fd5e387f078a716e49df62f894ce767700"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def duplicate_reject(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AssertionError(("duplicate JSON key", key))
        out[key] = value
    return out


def parse(data: bytes):
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=duplicate_reject,
                      parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(("nonfinite", value))))


def same_type(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_type(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_type(x, y) for x, y in zip(a, b))
    return a == b


def pin(path: Path, record: dict):
    data = path.read_bytes()
    assert len(data) == record["bytes"] and sha(data) == record["sha256"], str(path)
    return data


def git_tree(base: str):
    data = subprocess.check_output(["git", "ls-tree", "-rz", base], cwd=REPO)
    result = {}
    for row in data.split(b"\0"):
        if not row:
            continue
        info, path = row.split(b"\t", 1)
        mode, kind, oid = info.split()
        assert kind == b"blob" and path not in result
        result[path.decode("utf-8")] = oid.decode("ascii")
    return result


def git_pin(tree: dict, name: str, record: dict):
    data = subprocess.check_output(["git", "cat-file", "blob", tree[name]], cwd=REPO)
    assert len(data) == record["bytes"] and sha(data) == record["sha256"], name


def main():
    data = INDEX.read_bytes()
    assert len(data) == 318456 and sha(data) == INDEX_SHA
    doc = parse(data)
    assert doc["schema"] == "i03-var06-v101-retrospective-evidence-index/v1"
    assert doc["source_base_commit"] == BASE
    assert doc["publication_id"] == "I03.var06.out_duration_counterexample.readonly.1.0.1"
    assert doc["bounded_decision"] == "GO_BOUNDED_RETROSPECTIVE_COUNTEREXAMPLE"
    assert doc["original_v100_decision"] == "NO_GO_RUN" and doc["new_native_runs"] == 0
    assert doc["original_v100_process_exits"] == [0, 0, 0, 0, 0, 1]
    assert doc["independent_checks"] == 20433
    assert doc["parent_report_cells"] == doc["child_report_cells"] == 5210
    assert doc["corresponding_non_description_equal"] == 5209

    sources = doc["source_files"]
    assert len(sources) == doc["source_count"] == 258
    assert same_type(sources, doc["source"])
    names = [row["path"] for row in sources]
    assert len(set(names)) == len(names)
    for row in sources:
        relative = Path(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        pin(HERE / relative, row)
    source_by_name = {row["path"]: row for row in sources}

    raw = doc["raw_files"]
    assert len(raw) == doc["raw_record_count"] == 144
    assert len([r for r in raw if r["section"] == "failed_v100_run"]) == 26
    assert len([r for r in raw if r["section"] != "failed_v100_run"]) == 118
    for row in raw:
        path = Path(row["path"])
        pin(path if path.is_absolute() else REPO / path, row)

    tree = git_tree(BASE)
    refs = doc["accepted_source_refs"]
    assert len(refs) == 214 and len({r["path"] for r in refs}) == 214
    for row in refs:
        pin(REPO / row["path"], row["local_disk"])
        git_pin(tree, row["path"], row["published_git_at_base"])

    copies = (("v100_inert_source_copies", 117), ("root_context_small_copies", 30),
              ("root_independent_proof_copies", 5))
    for field, expected in copies:
        rows = doc[field]
        assert len(rows) == expected
        for row in rows:
            copy_name = row["owned_copy"]
            assert copy_name in source_by_name
            pin(HERE / copy_name, row)
            original = REPO / row["original"]
            if original.exists():
                pin(original, row)

    installed = doc["installed"]
    assert len(installed) == 3 and {r["role"] for r in installed} == {"exe", "manual", "dictionary"}
    for row in installed:
        pin(Path(row["path"]), row)

    history_name = "review/independent-development-history.json"
    history = parse(pin(HERE / history_name, source_by_name[history_name]))
    assert history["historical_file_count"] == len(history["historical_files"]) == 26
    assert len(history["active_files"]) == 4
    for row in history["historical_files"] + history["active_files"]:
        assert same_type(row, source_by_name[row["path"]])

    fixed = {"review/independent_replay.py": doc["independent_method_sha256"],
             "review/independent_self_check.py": doc["independent_self_check_sha256"],
             "review/independent-postrun-verdict.json": doc["independent_verdict_sha256"],
             "review/independent-postrun-go-2026-10-08.md": doc["independent_postrun_memo_sha256"],
             "contract.json": doc["contract_sha256"],
             "author-verdict.json": doc["author_verdict_sha256"]}
    for name, expected in fixed.items():
        assert source_by_name[name]["sha256"] == expected

    catalog = doc["catalog_history"]
    archive = HERE / catalog["owned_exact_archive"]
    archived = parse(pin(archive, catalog["local_disk_at_selection"]))
    git_pin(tree, catalog["path"], catalog["published_git_at_base"])
    live = parse((REPO / catalog["path"]).read_bytes())
    assert len(archived["entries"]) == 491 and len(live["entries"]) >= 491
    assert same_type(archived["entries"], live["entries"][:491])
    assert same_type({k: v for k, v in archived.items() if k != "entries"},
                     {k: v for k, v in live.items() if k != "entries"})
    ids = [row["publication_id"] for row in live["entries"]]
    assert len(ids) == len(set(ids))

    print(json.dumps({"decision": "GO_CONTENT_BYTE_AUDIT", "index_sha256": INDEX_SHA,
                      "sources": len(sources), "raw": len(raw), "accepted_dual_refs": len(refs),
                      "v100_inert_copies": 117, "context_copies": 30, "proof_copies": 5,
                      "installed": 3, "historical_reviewer_files": 26,
                      "catalog_live_entries": len(live["entries"])}, sort_keys=True))


if __name__ == "__main__":
    main()
