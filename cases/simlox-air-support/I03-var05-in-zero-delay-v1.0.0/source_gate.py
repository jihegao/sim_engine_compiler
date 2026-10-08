"""Read-only byte/source/raw and append-aware historical-catalog gate."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from build import construct, typed_equal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
DESIGN_SHA = "95ba77bcac344e023f140a39b4f88b4f94160d07c2a4e94563ff84de592f7331"
INPUT_SHA = "6803d02f8c113891bccaa5dd2f89a1b5c7807a5753fb4b7eeb170d3ac050cc08"
CONTEXT_SHA = "2b7528d1f977126892a7290a8c62d7742e85e11423f720789ece040b3af56a30"
RUN_ID = "i03-var05-in-zero-delay-v100-ssh-20261008-01"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, wanted: dict) -> dict:
    assert path.is_file(), ("missing mandatory original", str(path))
    got = pin(path.read_bytes())
    assert got == {k: wanted[k] for k in ("bytes", "sha256")}, (str(path), got, wanted)
    return got


def unique_json(data: bytes) -> object:
    def pairs(values: list[tuple[str, object]]) -> dict:
        out = {}
        for key, value in values:
            assert key not in out, ("duplicate JSON key", key)
            out[key] = value
        return out
    def finite_only(value: str) -> None:
        raise ValueError(("nonfinite JSON number", value))
    result = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=finite_only)
    def finite_walk(value: object) -> None:
        if type(value) is float:
            assert math.isfinite(value), "nonfinite/overflow JSON number"
        elif type(value) is dict:
            for child in value.values():
                finite_walk(child)
        elif type(value) is list:
            for child in value:
                finite_walk(child)
    finite_walk(result)
    return result


def git_tree(base: str) -> dict[str, str]:
    proc = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    result = {}
    for row in proc.stdout.split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            _, kind, oid = meta.split(b" ")
            assert kind == b"blob"
            path = name.decode("utf-8")
            assert path not in result
            result[path] = oid.decode("ascii")
    return result


def git_blob(tree: dict[str, str], path: str) -> bytes:
    assert path in tree, path
    proc = subprocess.run([str(GIT), "cat-file", "blob", tree[path]], cwd=REPO, capture_output=True)
    assert proc.returncode == 0, (path, proc.stderr.decode(errors="replace"))
    return proc.stdout


def catalog(design: dict, tree: dict[str, str], mode: str, archive: bytes) -> dict:
    source = design["source_lineage"]
    path = REPO / "cases/simlox-air-support/publication-index-v1.json"
    assert pin(archive) == source["catalog_local_point_time"]
    assert pin(git_blob(tree, path.relative_to(REPO).as_posix())) == \
           {key: source["catalog_git_base_blob"][key] for key in ("bytes", "sha256")}
    archived = unique_json(archive)
    live_data = path.read_bytes()
    if mode == "live":
        assert pin(live_data) == source["catalog_local_point_time"], "point-time live catalog changed before launch"
    live = unique_json(live_data)
    assert type(archived) is type(live) is dict
    assert type(archived["entries"]) is type(live["entries"]) is list
    assert len(archived["entries"]) == source["catalog_historical_entries"] == 494
    assert len(live["entries"]) >= 494
    assert typed_equal({k: v for k, v in archived.items() if k != "entries"},
                       {k: v for k, v in live.items() if k != "entries"})
    assert typed_equal(archived["entries"], live["entries"][:494])
    ids = [entry["publication_id"] for entry in live["entries"]]
    assert all(type(item) is str and item for item in ids) and len(ids) == len(set(ids))
    return {"historical_prefix_checked": 494, "live_entries_observed": len(live["entries"]),
            "archive_sha256": pin(archive)["sha256"]}


def context(design: dict) -> tuple[dict, bytes]:
    map_path = HERE / "context-custody-v2.json"
    assert check(map_path, {"bytes": 5104, "sha256": CONTEXT_SHA})
    mapping = unique_json(map_path.read_bytes())
    assert mapping["schema"] == "i03-var05-context-custody/v2"
    assert len(mapping["records"]) == 17
    declared = {row["path"]: row for row in design["source_lineage"]["design_history"]}
    paths = set()
    archive = None
    for row in mapping["records"]:
        original = row["original_path"]
        assert original not in paths
        paths.add(original)
        wanted = {k: row[k] for k in ("bytes", "sha256")}
        if original in declared:
            assert wanted == {k: declared[original][k] for k in ("bytes", "sha256")}
        copy_path = HERE / row["owned_copy"]
        check(copy_path, wanted)
        original_path = REPO / original
        assert row["original_if_present_must_match"] is (original != "cases/simlox-air-support/publication-index-v1.json")
        if original_path.exists() and row["original_if_present_must_match"]:
            check(original_path, wanted)
        if original == "cases/simlox-air-support/publication-index-v1.json":
            archive = copy_path.read_bytes()
    assert declared.keys() <= paths and archive is not None
    return {"owned_copies_checked": len(paths), "map_sha256": CONTEXT_SHA}, archive


def verify(mode: str = "live") -> dict:
    assert mode in ("live", "sealed")
    check(HERE / "contract.json", {"bytes": 121824, "sha256": DESIGN_SHA})
    design = unique_json((HERE / "contract.json").read_bytes())
    assert design["run_id_proposed_absent"] == RUN_ID
    tree = git_tree(design["source_lineage"]["base_commit"])
    counts = {"source_pairs": 0, "accepted_original_raw": 0, "required_docs": 0, "installed": 0}
    references = design["source_lineage"]["accepted_parent"]["all_source_refs"] + \
                 design["source_lineage"]["accepted_prerequisites"]["all_source_refs"]
    assert len(references) == 80 and len({row["path"] for row in references}) == 80
    for row in references:
        check(REPO / row["path"], row["disk"])
        assert pin(git_blob(tree, row["path"])) == row["git"]
        counts["source_pairs"] += 1
    for row in design["source_lineage"]["mandatory_original_raw"]:
        check(Path(row["path"]), row)
        counts["accepted_original_raw"] += 1
    for relative, wanted in design["source_lineage"]["required_docs"].items():
        check(REPO / relative, wanted)
        counts["required_docs"] += 1
    for key in ("installed_manual", "installed_dictionary", "installed_executable"):
        check(Path(design["source_lineage"][key]["path"]), design["source_lineage"][key])
        counts["installed"] += 1
    assert counts == {"source_pairs": 80, "accepted_original_raw": 112, "required_docs": 8, "installed": 3}
    helper_relative = "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/captured_process.ps1"
    helper_expected = {"bytes": (HERE / "captured_process.ps1").stat().st_size,
                       "sha256": "17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"}
    assert check(HERE / "captured_process.ps1", helper_expected) == helper_expected
    assert check(REPO / helper_relative, helper_expected) == helper_expected
    assert pin(git_blob(tree, helper_relative)) == helper_expected
    custody, archive = context(design)
    from copy_pure_proof import candidate as pure_custody_candidate
    pure_custody = pure_custody_candidate()
    assert len(pure_custody["records"]) == 26
    cat = catalog(design, tree, mode, archive)
    parent_path = REPO / design["source_lineage"]["accepted_parent"]["input"]["path"]
    parent = unique_json(parent_path.read_bytes())
    child_path = HERE / "native-input.json"
    check(child_path, {"bytes": 43550, "sha256": INPUT_SHA})
    assert typed_equal(unique_json(child_path.read_bytes()), construct(parent, design))
    run = HERE / "runs" / RUN_ID
    if mode == "live":
        assert not run.exists(), ("run already exists", str(run))
    return {"schema": "i03-var05-source-gate/v1", "mode": mode, "counts": counts,
            "catalog": cat, "context": custody, "pure_proof_copies_checked": 26,
            "run_absent_observed": not run.exists(),
            "input_sha256": INPUT_SHA, "contract_sha256": DESIGN_SHA}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    args = parser.parse_args()
    print(json.dumps(verify(args.mode), sort_keys=True))
