"""Read-only exact staged-byte and catalog audit for I03.var11."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1]
R = P.parents[2]
CASE = P.relative_to(R).as_posix()
CAT = "cases/simlox-air-support/publication-index-v1.json"
INDEX_SHA = "043d33cfae395a1b9ce8922f70bacc5be9239da6553973598d75af9ff551fc05"
ROOT_STAGE = R / "tmp/i03-var11-root-append-stage-proof-20261008"
ROOT_AUDIT = R / "tmp/i03-var11-root-staged-publication-audit-20261008.json"


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def typed(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    return a == b


def git(*args):
    return subprocess.check_output(["git", *args], cwd=R)


def obj(path):
    return json.loads(path.read_bytes())


root = obj(ROOT_STAGE / "receipt.json")
assert root["decision"] == "APPEND_STABLE_REPLAY_AND_EXACT_ALLOWLIST_STAGED"
assert root["staged_files"] == 246 and root["old_entries"] == 492 and root["new_entries"] == 493
assert root["independent_full_verdict_type_exact_unchanged"] is True
assert pin((ROOT_STAGE / "receipt.json").read_bytes())["sha256"] == "3f0d5cb7b1152f45927aeff4ccfe7ca60f18933aa488aba2542f1ff01caea77f"
assert pin((ROOT_STAGE / "staging-allowlist.nul").read_bytes()) == root["staging_allowlist"]
allow = [x.decode() for x in (ROOT_STAGE / "staging-allowlist.nul").read_bytes().split(b"\0") if x]
staged = [x.decode() for x in git("diff", "--cached", "--name-only", "-z").split(b"\0") if x]
assert len(allow) == len(staged) == 246 and set(allow) == set(staged)
assert len(set(staged)) == 246

idx_raw = (P / "evidence-index.json").read_bytes()
assert pin(idx_raw) == {"bytes": 385070, "sha256": INDEX_SHA}
idx = json.loads(idx_raw)
assert idx["source_count"] == 238 and idx["raw_record_count"] == 169
assert idx["approved_v1_reader_postrun_decision"] == "NO_GO_METHOD"
assert idx["independent_checks"] == 18550
assert (idx["parent_report_cells"], idx["child_report_cells"],
        idx["paired_non_description_cells"], idx["terminal_started_unarrived_task_quantity"],
        idx["terminal_completed_out_task_quantity"]) == (5210, 5210, 5209, 1, 0)
assert typed(idx["source"], idx["source_files"])
assert len(idx["source_files"]) == 238
source_paths = {f"{CASE}/{x['path']}" for x in idx["source_files"]}
review = set(root["extra_review_files"])
expected = source_paths | {f"{CASE}/evidence-index.json", CAT} | review
assert len(review) == 6 and len(expected) == 246 and expected == set(staged)

entries = {}
for item in git("ls-files", "--stage", "-z").split(b"\0"):
    if item:
        meta, path = item.split(b"\t", 1)
        mode, oid, stage = meta.split()
        name = path.decode()
        if name in expected:
            assert name not in entries and stage == b"0"
            entries[name] = oid.decode()
assert entries.keys() == expected
blob_cache = {}
for name in staged:
    oid = entries[name]
    if oid not in blob_cache:
        blob_cache[oid] = git("cat-file", "blob", oid)
    blob = blob_cache[oid]
    local = (R / name).read_bytes()
    if name != CAT:
        assert blob == local, name
    else:
        assert pin(local) == root["new_catalog_disk"]
        assert typed(json.loads(blob), json.loads(local))
for rec in idx["source_files"]:
    name = f"{CASE}/{rec['path']}"
    assert pin(blob_cache[entries[name]]) == {k: rec[k] for k in ("bytes", "sha256")}
assert pin(blob_cache[entries[f"{CASE}/evidence-index.json"]])["sha256"] == INDEX_SHA

archive = obj(P / "preserved-catalog/catalog-at-selection-492.bytes")
catalog_disk = obj(R / CAT)
catalog_git = json.loads(blob_cache[entries[CAT]])
assert len(archive["entries"]) == 492
for current in (catalog_disk, catalog_git):
    assert len(current["entries"]) == 493
    assert typed({k: v for k, v in current.items() if k != "entries"},
                 {k: v for k, v in archive.items() if k != "entries"})
    assert typed(current["entries"][:492], archive["entries"])
    ids = [x["publication_id"] for x in current["entries"]]
    assert len(ids) == len(set(ids)) == 493
    assert typed(current["entries"][-1], obj(P / "publication-entry.json"))
assert blob_cache[entries[CAT]] != (R / CAT).read_bytes()  # CRLF disk / LF Git are distinct.

for rec in idx["raw_files"]:
    assert pin(Path(rec["path"]).read_bytes()) == {k: rec[k] for k in ("bytes", "sha256")}
assert len(idx["raw_files"]) == 169
manifest = obj(P / "prelaunch-manifest.json")
assert len(manifest["source_files"]) == 782
for rec in manifest["source_files"]:
    assert pin(Path(rec["path"]).read_bytes()) == {k: rec[k] for k in ("bytes", "sha256")}
for rec in obj(P / "contract.json")["source_lineage"]["installed"]:
    assert pin(Path(rec["path"]).read_bytes()) == {k: rec[k] for k in ("bytes", "sha256")}

rr = obj(ROOT_AUDIT)
assert rr["decision"] == "EXACT_BYTES_SOURCE_RAW_CUSTODY_PASS"
assert rr["phase"] == "staged" and rr["ref"] == "INDEX"
assert rr["source_count"] == 238 and rr["mandatory_original_records"] == 169
assert rr["accepted_disk_git_pairs"] == 452 and rr["frozen_source_records"] == 782

run = subprocess.run([sys.executable, "-X", "utf8", "-B", str(P / "review/independent_replay_v2.py")],
                     cwd=R, capture_output=True)
assert run.returncode == 0 and run.stderr == b""
assert pin(run.stdout)["sha256"] == "fa7c577ba115340d4d153390e2408a5970adeff871cc20ade99e77e4a2be30fc"
assert typed(json.loads(run.stdout), obj(P / "review/independent-postrun-verdict-v2.json"))
print(json.dumps({"decision": "GO_STAGED", "staged_paths": 246,
                  "case_staged_blobs": 245, "indexed_sources": 238,
                  "mandatory_original_raw": 169, "manifest_source_records": 782,
                  "catalog_entries": 493, "catalog_disk_sha256": pin((R / CAT).read_bytes())["sha256"],
                  "catalog_git_sha256": pin(blob_cache[entries[CAT]])["sha256"],
                  "independent_checks_after_append": 18550,
                  "index_sha256": INDEX_SHA, "native_calls": 0}, separators=(",", ":")))
