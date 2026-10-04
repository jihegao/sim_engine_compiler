"""Read-only audit of published case-source SHA pins against disk and a Git ref.

This checks source maps in evidence indexes. Ignored native run files are counted
as skipped here; their package-specific raw seals require separate replay.
Pin definitions come from current working-tree indexes, so compare a historical
Git ref only when those index definitions are unchanged from that ref.
"""
import argparse
import collections
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CASES = REPO / "cases/simlox-air-support"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def collect():
    tracked = set(filter(None, git("ls-files", "-z").decode("utf-8").split("\0")))
    indexes = git("ls-files", "cases/simlox-air-support/*/evidence-index.json").decode("utf-8").splitlines()
    entries = []
    skipped = collections.Counter()

    for index_rel in indexes:
        index = json.loads((REPO / index_rel).read_text(encoding="utf-8-sig"))
        base = (REPO / index_rel).parent

        def add(name, pin, kind):
            if isinstance(pin, str):
                pin = {"sha256": pin}
            if not isinstance(pin, dict) or "sha256" not in pin:
                skipped["unsupported_pin"] += 1
                return
            path = Path(pin.get("path", name))
            if not path.is_absolute():
                path = base / path
            try:
                rel = path.resolve().relative_to(REPO).as_posix()
            except ValueError:
                skipped["outside_repo"] += 1
                return
            if rel not in tracked:
                skipped["untracked_or_ignored"] += 1
                return
            entries.append({"path": rel, "index": index_rel, "kind": kind,
                            "sha256": pin["sha256"], "bytes": pin.get("bytes")})

        source = index.get("source")
        if isinstance(source, list):
            for pin in source:
                add(pin.get("path", ""), pin, "source_list")
        elif isinstance(source, dict):
            for name, pin in source.items():
                if isinstance(pin, dict) and "sha256" in pin:
                    add(name, pin, "source_dict")
                elif isinstance(pin, dict):
                    for subname, nested in pin.items():
                        versioned = CASES / (base.name.rsplit("-", 1)[0] + "-" + name) / subname
                        add(str(versioned), nested, "source_nested")
        for key in ("source_files_sha256", "files_sha256", "files"):
            if isinstance(index.get(key), dict):
                for name, pin in index[key].items():
                    add(name, pin, key)
    return indexes, entries, skipped


def git_blobs(ref, paths):
    tree = (git("ls-files", "--stage", "-z", "cases/simlox-air-support")
            if ref == "INDEX" else
            git("ls-tree", "-r", "-z", ref, "--", "cases/simlox-air-support"))
    object_ids = {}
    for item in tree.split(b"\0"):
        if item:
            meta, name = item.split(b"\t", 1)
            parts = meta.split()
            if ref == "INDEX" and parts[2] != b"0":
                continue
            object_ids[name.decode("utf-8")] = parts[1 if ref == "INDEX" else 2].decode("ascii")
    wanted = list(dict.fromkeys(object_ids[path] for path in paths if path in object_ids))
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=REPO,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = proc.communicate(("\n".join(wanted) + "\n").encode("ascii"))
    if proc.returncode:
        raise RuntimeError(error.decode("utf-8", errors="replace"))
    blobs = {}
    position = 0
    for object_id in wanted:
        end = output.index(b"\n", position)
        size = int(output[position:end].split()[2])
        start = end + 1
        blobs[object_id] = output[start:start + size]
        position = start + size + 1
    return object_ids, blobs


def seal(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def audit(ref):
    indexes, entries, skipped = collect()
    paths = {entry["path"] for entry in entries}
    object_ids, blobs = git_blobs(ref, paths)
    mismatches = []
    disk_mismatches = []
    missing_git = []
    for entry in entries:
        path = entry["path"]
        disk = (REPO / path).read_bytes()
        disk_seal = seal(disk)
        expected = {"sha256": entry["sha256"], "bytes": entry["bytes"]}
        disk_ok = disk_seal["sha256"] == entry["sha256"] and (entry["bytes"] is None or disk_seal["bytes"] == entry["bytes"])
        if not disk_ok:
            disk_mismatches.append({**entry, "actual": disk_seal})
        object_id = object_ids.get(path)
        if object_id is None:
            missing_git.append(entry)
            continue
        published = blobs[object_id]
        published_seal = seal(published)
        git_ok = published_seal["sha256"] == entry["sha256"] and (entry["bytes"] is None or published_seal["bytes"] == entry["bytes"])
        if not git_ok:
            mismatches.append({"path": path, "index": entry["index"], "kind": entry["kind"],
                               "expected": expected, "published": published_seal,
                               "crlf_to_lf_only": disk.replace(b"\r\n", b"\n") == published})
    return {"schema": "simlox-published-source-byte-audit/v1", "ref": ref,
            "indexes_examined": len(indexes), "source_pins_examined": len(entries),
            "unique_files_examined": len(paths), "skipped": dict(skipped),
            "disk_mismatches": disk_mismatches, "missing_git": missing_git,
            "git_mismatches": mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="origin/simlox/main")
    parser.add_argument("--staged", action="store_true", help="compare with the Git index instead of a ref")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = "INDEX" if args.staged else args.ref
    result = audit(target)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    groups = collections.Counter(Path(item["path"]).parent.as_posix() for item in result["git_mismatches"])
    print(json.dumps({"ref": target, "indexes": result["indexes_examined"],
                      "pins": result["source_pins_examined"], "disk_bad": len(result["disk_mismatches"]),
                      "git_missing": len(result["missing_git"]), "git_bad": len(result["git_mismatches"]),
                      "crlf_only": sum(item["crlf_to_lf_only"] for item in result["git_mismatches"]),
                      "groups": groups}, indent=2))
    if result["disk_mismatches"] or result["missing_git"] or result["git_mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
