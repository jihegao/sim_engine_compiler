"""P1/P2 repair: exact publication identity and immutable artifact-byte snapshots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import datetime

from publication_target_v1 import BindingError, published_index, require, require_stable_refs, verify
from publication_snapshot_v2 import derive_captured_reader, parse_artifact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BINDING = HERE / "publication-binding-v1.json"
BINDING_SHA256 = "a94dec581bece6bcda06c9c2cbd8606c790ae89457cc0bf28c835a9339d6352b"
ALLOWED_ORIGINS = {
    "git@github.com:jihegao/sim_engine_compiler.git",
    "https://github.com/jihegao/sim_engine_compiler.git",
    "https://github.com/jihegao/sim_engine_compiler",
    "ssh://git@github.com/jihegao/sim_engine_compiler.git",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args, accept=(0,)):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1")
    result = subprocess.run(["git", "--no-replace-objects", *args], cwd=ROOT, env=env, capture_output=True)
    require(result.returncode in accept, "GIT_OBSERVATION_FAILED", f"{args[0]} exit {result.returncode}; {result.stderr.decode('utf-8', errors='replace')[:400]}")
    return result


def describe(commit):
    require(git("cat-file", "-t", commit).stdout.strip() == b"commit", "NOT_COMMIT_OBJECT", commit)
    lines = git("cat-file", "-p", commit).stdout.decode("utf-8").split("\n\n", 1)[0].splitlines()
    trees = [line[5:] for line in lines if line.startswith("tree ")]
    require(len(trees) == 1, "COMMIT_TREE_HEADER", commit)
    return {"tree": trees[0], "parents": [line[7:] for line in lines if line.startswith("parent ")]}


def ancestor(older, newer):
    return git("merge-base", "--is-ancestor", older, newer, accept=(0, 1)).returncode == 0


def refs():
    return git("ls-remote", "--refs", "origin", "refs/heads/main", "refs/heads/simlox/main").stdout.decode("ascii")


def run(mode, target_path=None, product_path=None):
    require(not sys.flags.optimize, "ASSERTS_DISABLED", "run without -O/-OO")
    binding_bytes = BINDING.read_bytes()
    require(digest(binding_bytes) == BINDING_SHA256, "IMMUTABLE_BINDING_CHANGED", str(BINDING))
    binding = parse_artifact(binding_bytes)
    target_bytes = Path(target_path).read_bytes() if target_path is not None else None
    product_bytes = Path(product_path).read_bytes() if product_path is not None else None
    target = parse_artifact(target_bytes) if target_bytes is not None else None
    product_target = parse_artifact(product_bytes) if product_bytes is not None else None
    artifacts = [(BINDING, binding_bytes)]
    if target_path is not None:
        artifacts.append((Path(target_path), target_bytes))
    if product_path is not None:
        artifacts.append((Path(product_path), product_bytes))
    origin = git("remote", "get-url", "origin").stdout.decode("utf-8").strip()
    require(origin in ALLOWED_ORIGINS, "REMOTE_REPOSITORY_MISMATCH", origin)
    before = refs()
    identity = verify(binding, before, describe, ancestor, mode, target, BINDING_SHA256, product_target)
    # Source/version provenance belongs to the immutable actual publication, not local index alone.
    for name in ("input", "manifest", "inherited_reader"):
        source = binding[name]
        local = ROOT / source["path"]
        require(digest(local.read_bytes()) == source["sha256"], "LOCAL_SOURCE_MISMATCH", name)
        committed = git("show", binding["publication"]["commit"] + ":" + source["path"]).stdout
        require(digest(committed) == source["sha256"], "PUBLISHED_SOURCE_MISMATCH", name)
    inherited = ROOT / binding["inherited_reader"]["path"]
    snapshot_reader = HERE / "original-published-snapshot-reader-v3.py"
    require(snapshot_reader.read_text(encoding="utf-8") == derive_captured_reader(inherited.read_text(encoding="utf-8"), BINDING_SHA256), "RAW_DERIVATION_CHANGED", "only four approved source replacements allowed")
    published_index(binding, lambda commit, path: git("show", commit + ":" + path).stdout)
    # -E ignores inherited PYTHONOPTIMIZE; all original raw assertions remain. Never relay raw GO.
    child = subprocess.run([sys.executable, "-E", "-X", "utf8", "-B", str(snapshot_reader)], input=binding_bytes, cwd=ROOT, env={k:v for k,v in os.environ.items() if k not in ("PYTHONOPTIMIZE", "PYTHONPATH", "PYTHONHOME")}, capture_output=True)
    require(child.returncode == 0 and not child.stderr, "ORIGINAL_RAW_REPLAY_FAILED", f"exit={child.returncode}; stderrSHA256={digest(child.stderr)}")
    try:
        raw = json.loads(child.stdout)
    except (ValueError, UnicodeError) as exc:
        raise BindingError("INVALID_RAW_RECEIPT", str(exc)) from exc
    require(raw.get("decision") == "GO_BOUNDED_PUBLISHED_SNAPSHOT_RAW_REPLAY", "RAW_DECISION", "unexpected subordinate decision")
    require(raw.get("run_id") == binding["run_id"] and raw.get("source_roles") == 140 and raw.get("readonly_pairs") == 25, "RAW_PROVENANCE", "wrong source/version/run custody")
    require(raw.get("native_calls_by_reviewer") == 0 and raw.get("all_commands_terminal") is True, "RAW_EXECUTION_BOUNDARY", "unexpected calls or incomplete checker")
    after = refs()
    require_stable_refs(before, raw.get("remote_refs", ""), after)
    # Re-inspect actual object/ancestry with the terminal observed ref before emitting a v2 GO.
    require(identity == verify(binding, after, describe, ancestor, mode, target, BINDING_SHA256, product_target), "IDENTITY_CHANGED", "terminal identity differs")
    for path, captured_bytes in artifacts:
        require(path.read_bytes() == captured_bytes, "BINDING_ARTIFACT_CHANGED", str(path))
    raw.pop("decision")
    decision = "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY" if mode == "current-target" else "GO_BOUNDED_HISTORICAL_PUBLICATION_READONLY_REPLAY"
    return {"schema": "simlox-postpublication-replay/v3", "decision": decision,
            "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "publication_identity": identity,
            "origin_url": origin, "publication_binding_sha256": BINDING_SHA256,
            "explicit_target_binding": str(target_path) if target_path else None,
            "explicit_target_binding_sha256": digest(target_bytes) if target_bytes is not None else None,
            "explicit_product_binding": str(product_path) if product_path else None,
            "explicit_product_binding_sha256": digest(product_bytes) if product_bytes is not None else None,
            "reader_v3_sha256": digest(Path(__file__).read_bytes()), "gate_sha256": digest((HERE / "publication_target_v1.py").read_bytes()),
            "snapshot_reader_sha256": digest(snapshot_reader.read_bytes()), "immutable_published_index_sha256": binding["publication_index"]["sha256"],
            "snapshot_protocol_sha256": digest((HERE / "publication_snapshot_v2.py").read_bytes()),
            "subordinate_binding_transport": "captured-stdin-bytes",
            "subordinate_stdout_sha256": digest(child.stdout), "subordinate_raw_evidence": raw,
            "remote_refs_before": before, "remote_refs_after": after,
            "native_calls": 0, "whole_variant_pass": False, "wholeGoalComplete": False, "effective_nonGUI_denominator": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("current-target", "historical-publication"), default="current-target")
    parser.add_argument("--target-binding", type=Path, help="Explicit independently reviewed later-target JSON; current-target only")
    parser.add_argument("--product-binding", type=Path, help="Explicit independently verified external product commit/tree; both modes")
    args = parser.parse_args()
    try:
        result = run(args.mode, args.target_binding, args.product_binding)
    except Exception as exc:
        result = {"schema": "simlox-postpublication-replay/v3", "decision": "NO_GO_POSTPUBLICATION",
                  "code": getattr(exc, "code", type(exc).__name__), "error": str(exc), "native_calls": 0}
        print(json.dumps(result))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
