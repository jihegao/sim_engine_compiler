#!/usr/bin/env python3
"""Recompute the historical negative result from the small committed selection."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile

try:
    from benchmarks.three_arm_v1 import summarize
except ModuleNotFoundError:
    import summarize


PREFIX = "runs/three-arm-v1/formal/"
ARCHIVE_NAME = "formal-measurements.tar.gz"
MAX_ARCHIVE_BYTES = 128 * 1024
MAX_TAR_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
EXPECTED_MEMBERS = {PREFIX + name for name in ("manifest.json", "manifest.sha256", "state.json")}
EXPECTED_MEMBERS.update(
    PREFIX + f"measurement/cell-{ordinal:03d}/{name}"
    for ordinal in range(99)
    for name in ("record.json", "stage-c-report.json", "gnu-time.txt")
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_selection(folder: Path) -> dict:
    """Read bytes and temporary evidence only; never launch a process or model."""
    evidence = json.loads((folder / "EVIDENCE.json").read_text())
    selection = evidence["committed_selection"]
    if selection.get("path") != ARCHIVE_NAME or selection.get("members") != 300:
        raise ValueError("unsupported committed selection")
    with (folder / ARCHIVE_NAME).open("rb") as source:
        raw = source.read(MAX_ARCHIVE_BYTES + 1)
    if (len(raw) > MAX_ARCHIVE_BYTES or len(raw) != selection.get("bytes")
            or _sha256(raw) != selection.get("sha256")):
        raise ValueError("selection archive size or hash mismatch")
    # Bound decompression before parsing tar headers, including hidden PAX data.
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
        tar_bytes = compressed.read(MAX_TAR_BYTES + 1)
    if len(tar_bytes) > MAX_TAR_BYTES:
        raise ValueError("selection decompressed tar exceeds bound")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        for member in archive:
            if (member.name not in EXPECTED_MEMBERS or member.name in files
                    or not member.isfile() or member.size > MAX_FILE_BYTES):
                raise ValueError("unsafe, duplicate or unexpected selected member")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("selected member is not readable")
            data = source.read(MAX_FILE_BYTES + 1)
            identity = evidence["files"].get(member.name)
            if identity != {"bytes": len(data), "sha256": _sha256(data)}:
                raise ValueError(f"selected member differs from original catalog: {member.name}")
            files[member.name] = data
    if set(files) != EXPECTED_MEMBERS:
        raise ValueError("selected measurement membership is incomplete")
    if sum(map(len, files.values())) != selection.get("uncompressed_bytes"):
        raise ValueError("selected uncompressed byte count mismatch")
    manifest = json.loads(files[PREFIX + "manifest.json"])
    if manifest.get("source_commit") != evidence.get("measured_source_commit"):
        raise ValueError("selected measured source identity mismatch")
    if _sha256(files[PREFIX + "state.json"]) != evidence["redaction"]["published_state_sha256"]:
        raise ValueError("selected state differs from historical redaction receipt")
    with tempfile.TemporaryDirectory(prefix="three-arm-publication-") as directory:
        base = Path(directory)
        # Exact finite names above make writing these regular files safe. Do not
        # extract an arbitrary archive or resolve historical absolute source paths.
        for name, data in files.items():
            destination = base / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        result = summarize.summarize(base / PREFIX)
    expected = json.loads((folder / "summary.json").read_text())
    if result != expected:
        raise ValueError("recomputed historical summary differs from committed summary")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    result = verify_selection(parser.parse_args().folder)
    classifications = [row["classification"] for group in result["groups"]
                       for row in group["comparisons"]]
    print(json.dumps({
        "status": result["formal_status"],
        "completed": result["complete_cells"], "planned": result["planned_cells"],
        "bounded_benefit": classifications.count("bounded-benefit"),
        "regression": classifications.count("regression"),
        "no_demonstrated_benefit": classifications.count("no-demonstrated-benefit"),
        "fresh_simulation_or_timing": False,
    }))


if __name__ == "__main__":
    main()
