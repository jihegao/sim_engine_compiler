"""Read-only independent preindex custody and scope audit for I03.var11."""
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parents[1]
R = P.parents[2]
BASE = "50c552285f69e0b5a8bf82a8cdc6999b9e68f7cf"
EXPECTED_DRY = "043d33cfae395a1b9ce8922f70bacc5be9239da6553973598d75af9ff551fc05"
EXCLUDE = ("review/independent-content", "review/independent-staged",
           "review/independent-remote", "review/independent-pr-")
ADDED = (
    "prelaunch-manifest.json", "postrun_context.py", "postrun-context-custody.json",
    "review_proof_context.py", "independent-postrun-proof-custody.json",
    "make_raw_custody.py", "raw-custody-map.json", "postrun_audit.py",
    "author-postrun-verdict.json", "make_evidence_index.py", "README-publication.md",
    "REPRODUCTION-postrun.md", "cli-scope-signoff-2026-10-08.md", "publication-entry.json",
    "preserved-postrun-development/postrun-audit-tuple-json-draft.py.bytes",
    "review/preflight-ssh0-20261007T210756239Z.json",
    "review/independent-prelaunch-go.json", "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent_replay_v2.py", "review/independent-postrun-verdict-v2.json",
    "review/independent-postrun-go-v2-2026-10-08.md",
    "review/independent-postrun-v1-no-go-2026-10-08.md",
)


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(path, rec):
    assert path.is_file(), path
    assert pin(path.read_bytes()) == {k: rec[k] for k in ("bytes", "sha256")}, path


def typed(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    return a == b


def obj(path):
    return json.loads(path.read_bytes())


contract = obj(P / "contract.json")
assert pin((P / "contract.json").read_bytes())["sha256"] == "67bef26d4fdec4d34e88b20e177239fb973aeba7152f72d26d4d9f9a4f9a79c1"
lin = contract["source_lineage"]
manifest = obj(P / "prelaunch-manifest.json")
assert pin((P / "prelaunch-manifest.json").read_bytes())["sha256"] == "4aa438b946ff43b2e76f21eb1888f50ee976d1444cb568e5f52c13917f7703fe"
assert len(manifest["source_files"]) == 782
for rec in manifest["source_files"]:
    exact(Path(rec["path"]), rec)
old_owned = {Path(r["path"]).relative_to(P).as_posix() for r in manifest["source_files"]
             if Path(r["path"]).is_relative_to(P)}
assert len(old_owned) == 175

additional = set(ADDED)
for mapping, number in (("postrun-context-custody.json", 32),
                        ("independent-postrun-proof-custody.json", 9)):
    rows = obj(P / mapping)["records"]
    assert len(rows) == number
    for row in rows:
        assert set(row) == {"original", "owned_copy", "bytes", "sha256"}
        exact(P / row["owned_copy"], row)
        original = R / row["original"]
        if original.exists():
            exact(original, row)
        additional.add(row["owned_copy"])
assert old_owned.isdisjoint(additional)
expected_names = old_owned | additional
actual_names = {p.relative_to(P).as_posix() for p in P.rglob("*") if p.is_file()
                and not any(x in {"runs", "transport-evidence", "test-output", "__pycache__"}
                            for x in p.relative_to(P).parts)
                and p.name != "evidence-index.json"
                and not any(p.relative_to(P).as_posix().startswith(prefix) for prefix in EXCLUDE)}
assert expected_names == actual_names, {"extra": sorted(actual_names - expected_names),
                                        "missing": sorted(expected_names - actual_names)}
assert len(expected_names) == 238

raw = obj(P / "raw-custody-map.json")
assert raw["original_paths_mandatory"] is True and len(raw["records"]) == 169
assert (raw["accepted_context"], raw["excluded_failed_witness"], raw["new_child_raw"],
        raw["new_child_invocation_and_closure"]) == (118, 26, 23, 2)
assert len({x["path"] for x in raw["records"]}) == 169
for rec in raw["records"]:
    exact(Path(rec["path"]), rec)
classes = Counter(x["classification"] for x in raw["records"])
assert classes["accepted_or_required_context"] == 118
assert classes["excluded_failed_witness"] == 26
assert sum(v for k, v in classes.items() if k.startswith("new_child")) == 25
prior = {x["path"] for x in lin["original_raw"]}
assert prior == {x["path"] for x in raw["records"] if x["classification"] != "new_child_raw" and not x["classification"].startswith("new_child")}

refs = lin["primary_parent_source_and_secondary_context_source_disk_vs_git_at_base"]
assert len(refs) == lin["source_ref_count"] == 452
tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASE], cwd=R)
git_oids = {}
for line in tree.split(b"\0"):
    if line:
        meta, name = line.split(b"\t", 1)
        mode, kind, oid = meta.split()
        if kind == b"blob":
            git_oids[name.decode()] = oid.decode()
blob_cache = {}
for rec in refs:
    exact(R / rec["path"], rec["local_disk"])
    oid = git_oids[rec["path"]]
    if oid not in blob_cache:
        blob_cache[oid] = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=R)
    assert pin(blob_cache[oid]) == rec["published_git_at_base"], rec["path"]
for rec in lin["installed"]:
    exact(Path(rec["path"]), rec)

cat = lin["catalog_at_selection"]
archive_bytes = (P / cat["owned_exact_archive"]).read_bytes()
assert pin(archive_bytes) == cat["local_disk"]
archive = json.loads(archive_bytes)
live = obj(R / cat["path"])
assert len(archive["entries"]) == cat["entry_count"] == 492
assert len(live["entries"]) >= 492
assert typed({k: v for k, v in archive.items() if k != "entries"},
             {k: v for k, v in live.items() if k != "entries"})
assert typed(archive["entries"], live["entries"][:492])
ids = [x["publication_id"] for x in live["entries"]]
assert len(ids) == len(set(ids))
cat_oid = git_oids[cat["path"]]
if cat_oid not in blob_cache:
    blob_cache[cat_oid] = subprocess.check_output(["git", "cat-file", "blob", cat_oid], cwd=R)
assert pin(blob_cache[cat_oid]) == cat["published_git_at_base"]
synthetic = copy.deepcopy(archive)
synthetic["entries"].append({"publication_id": "independent.probe.unique"})
assert typed(archive["entries"], synthetic["entries"][:492]) and len(synthetic["entries"]) == 493

assert pin((P / "review/independent_replay.py").read_bytes())["sha256"] == "08e64f0095a9cedfea45a4253418c844bf64c66aa15a4790b665ee4cde740170"
assert pin((P / "review/independent_replay_v2.py").read_bytes())["sha256"] == "381bc37e89b6ebfc6a0b3d0cc35752d1a29f42beb5ac739752ee8a97675f7cf0"
assert pin((P / "review/independent-postrun-v1-no-go-2026-10-08.md").read_bytes())["sha256"] == "947bb723a61883887e15d0019013b9f919fc32552920345aefde1b8ec68225af"
assert pin((P / "review/independent-postrun-verdict-v2.json").read_bytes())["sha256"] == "fa7c577ba115340d4d153390e2408a5970adeff871cc20ade99e77e4a2be30fc"
assert pin((P / "review/independent-postrun-go-v2-2026-10-08.md").read_bytes())["sha256"] == "088359633ead06d772c457e8d4c0f13b55246a58181c65f2660dc175a82af516"
old_fail = [r for r in obj(P / "postrun-context-custody.json")["records"]
            if r["original"].endswith("postrun-proof-v1/replay.stderr.bin")]
assert len(old_fail) == 1 and old_fail[0]["sha256"] == "f25c8e495512088117937d5d339a7e319c4952fcfae8ad6707a9ad0ec462078d"
v2_out = [r for r in obj(P / "independent-postrun-proof-custody.json")["records"]
          if r["original"].endswith("postrun-proof-v2/replay.stdout.bin")]
assert len(v2_out) == 1 and v2_out[0]["sha256"] == "fa7c577ba115340d4d153390e2408a5970adeff871cc20ade99e77e4a2be30fc"

sys.path.insert(0, str(P))
import make_evidence_index as author_index
candidate = author_index.build()
assert candidate["source_count"] == 238 and candidate["raw_record_count"] == 169
assert {r["path"] for r in candidate["source_files"]} == expected_names
assert typed(candidate["source"], candidate["source_files"])
assert typed(candidate["raw_files"], raw["records"])
assert candidate["approved_v1_reader_postrun_decision"] == "NO_GO_METHOD"
assert candidate["independent_checks"] == 18550
assert candidate["parent_report_cells"] == candidate["child_report_cells"] == 5210
assert candidate["paired_non_description_cells"] == 5209
assert candidate["terminal_started_unarrived_task_quantity"] == 1
assert candidate["terminal_completed_out_task_quantity"] == 0
assert candidate["catalog_history"]["required_prefix_entries"] == 492
assert "h46 is arithmetic only" in candidate["limits"][0]
data = (json.dumps(candidate, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
assert len(data) == 385070 and pin(data)["sha256"] == EXPECTED_DRY
assert not (P / "evidence-index.json").exists()
print(json.dumps({"decision": "GO_PREINDEX", "source_files": 238,
                  "manifest_source_files": 782, "accepted_source_refs": 452,
                  "mandatory_original_raw": 169, "postrun_context_copies": 32,
                  "independent_proof_copies": 9, "catalog_prefix": 492,
                  "candidate_bytes": len(data), "candidate_sha256": pin(data)["sha256"],
                  "native_calls": 0}, separators=(",", ":")))
