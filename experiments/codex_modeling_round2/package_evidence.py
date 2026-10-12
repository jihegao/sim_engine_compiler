#!/usr/bin/env python3
"""Package completed raw runs without modifying inputs, submissions or scorers.

Archive members are ordinary files relative to this experiment directory.
Paths are sorted and tar ownership, permissions, timestamps and gzip timestamps
are normalized. Python/zlib implementation changes can affect compressed bytes.
The original raw files remain in place. Run this only after all runs finish.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile


HERE = Path(__file__).resolve().parent
ROOTS = (
    "results/raw",
    "feedback",
    "calibration/internal",
    "repair/private/evidence",
    "repair/private/feedback-verification",
    "repair/feedback",
)
ARCHIVE = HERE / "results/evidence.tar.gz"
MANIFEST = HERE / "results/evidence-manifest.json"
VERIFICATION = HERE / "results/evidence-verification.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(name):
    path = PurePosixPath(name)
    require(bool(name) and not path.is_absolute() and "\\" not in name
            and all(part not in ("", ".", "..") for part in name.split("/"))
            and str(path) == name, f"unsafe member path: {name!r}")
    require(any(name.startswith(root + "/") for root in ROOTS),
            f"member is outside the approved raw roots: {name}")


def excluded(path):
    return "__pycache__" in path.parts or path.name.endswith(".pyc")


def raw_files():
    files = {}
    for root_name in ROOTS:
        root = HERE / root_name
        require(root.is_dir() and not root.is_symlink(), f"missing/linked root: {root_name}")
        for path in root.rglob("*"):
            relative = path.relative_to(HERE)
            if excluded(relative):
                continue
            require(not path.is_symlink(), f"symbolic link in evidence: {relative}")
            if path.is_dir():
                continue
            require(stat.S_ISREG(path.stat().st_mode), f"nonregular evidence: {relative}")
            name = relative.as_posix()
            safe_path(name)
            require(name not in files, f"duplicate input path: {name}")
            files[name] = path
    require(bool(files), "no raw evidence found")
    return dict(sorted(files.items()))


def sha256_file(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                      allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify(manifest, archive=ARCHIVE):
    expected = manifest["files"]
    require(sha256_file(archive) == manifest["archive"]["sha256"], "archive SHA-256 mismatch")
    require(archive.stat().st_size == manifest["archive"]["bytes"], "archive size mismatch")
    with archive.open("rb") as stream:
        header = stream.read(10)
    require(header[:3] == b"\x1f\x8b\x08" and header[4:8] == b"\x00" * 4,
            "gzip header lacks normalized timestamp")
    require(header[3] == 0, "gzip header unexpectedly contains a filename or other optional fields")

    seen = []
    verified_bytes = 0
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            safe_path(member.name)
            require(member.isfile() and not member.issym() and not member.islnk(),
                    f"nonregular archive member: {member.name}")
            require(member.name in expected, f"unexpected archive member: {member.name}")
            require(member.uid == member.gid == member.mtime == 0
                    and member.uname == member.gname == "" and member.mode == 0o644,
                    f"nondeterministic member metadata: {member.name}")
            require(not any(k in member.pax_headers for k in ("mtime", "atime", "ctime")),
                    f"unexpected PAX timestamp: {member.name}")
            source = tar.extractfile(member)
            require(source is not None, f"unreadable member: {member.name}")
            with source:
                content = source.read()
            require(len(content) == member.size == expected[member.name]["bytes"],
                    f"member size mismatch: {member.name}")
            require(hashlib.sha256(content).hexdigest() == expected[member.name]["sha256"],
                    f"member SHA-256 mismatch: {member.name}")
            seen.append(member.name)
            verified_bytes += len(content)
    require(seen == sorted(expected), "archive members missing, duplicated, or out of order")
    require(len(seen) == manifest["archive"]["member_count"], "archive member count mismatch")
    require(verified_bytes == manifest["total_uncompressed_file_bytes"], "total raw size mismatch")

    originals = raw_files()
    require(list(originals) == sorted(expected), "raw file set changed while packaging")
    for name, path in originals.items():
        require(path.stat().st_size == expected[name]["bytes"]
                and sha256_file(path) == expected[name]["sha256"],
                f"raw file changed while packaging: {name}")
    return {
        "schema": "codex-modeling-round2-evidence-verification/v1",
        "verified": True,
        "archive": "results/evidence.tar.gz",
        "archive_sha256": manifest["archive"]["sha256"],
        "archive_bytes": manifest["archive"]["bytes"],
        "members_verified": len(seen),
        "original_files_verified": len(originals),
        "uncompressed_file_bytes_verified": verified_bytes,
        "all_member_paths_safe": True,
        "all_members_regular_files": True,
        "member_order_sorted": True,
        "tar_metadata_normalized": True,
        "gzip_mtime_zero_and_filename_absent": True,
        "all_member_hashes_and_sizes_match_manifest": True,
        "original_raw_files_retained_and_unchanged": True,
        "verification_method": "Read and hash every archive member; rehash every original raw file.",
    }


def package():
    files = raw_files()
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="evidence.", suffix=".tar.gz.tmp", dir=ARCHIVE.parent)
    metadata = {}
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as tar:
                    for name, path in files.items():
                        content = path.read_bytes()
                        metadata[name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
                        member = tarfile.TarInfo(name)
                        member.size = len(content)
                        member.mtime = member.uid = member.gid = 0
                        member.uname = member.gname = ""
                        member.mode = 0o644
                        member.pax_headers = {}
                        tar.addfile(member, io.BytesIO(content))
        temp_path = Path(temporary)
        manifest = {
            "schema": "codex-modeling-round2-evidence-manifest/v1",
            "archive": {"path": "results/evidence.tar.gz", "sha256": sha256_file(temp_path),
                        "bytes": temp_path.stat().st_size, "member_count": len(metadata)},
            "raw_roots": list(ROOTS),
            "excluded": ["**/__pycache__/**", "**/*.pyc"],
            "member_paths_relative_to": "experiments/codex_modeling_round2",
            "total_uncompressed_file_bytes": sum(item["bytes"] for item in metadata.values()),
            "compression": {"format": "tar+gzip", "gzip_level": 9, "gzip_mtime": 0,
                            "gzip_filename": "", "tar_format": "PAX", "file_mode": "0644",
                            "uid": 0, "gid": 0, "mtime": 0},
            "files": metadata,
        }
        verification = verify(manifest, temp_path)
        os.replace(temporary, ARCHIVE)
        atomic_json(MANIFEST, manifest)
        atomic_json(VERIFICATION, verification)
        return verification
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Verify saved archive, manifest, and retained raw files.")
    args = parser.parse_args()
    if args.verify_only:
        verification = verify(json.loads(MANIFEST.read_text(encoding="utf-8")))
        atomic_json(VERIFICATION, verification)
    else:
        verification = package()
    print(json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
