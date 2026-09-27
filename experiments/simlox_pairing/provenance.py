"""Externally pinned source handoff and executable-source identities."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
import runpy
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "595cb5eee9987324b19a8c3566f201f937e05f15"
BASELINE_BUILD_SHA256 = "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1"
DEPENDENCY = "519b2094c3be355399bc101cdcfe30d456cbb47b"
MANIFEST_SHA256 = "0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987"
DELIVERED_ZIP_SHA256 = "fe5555954cc6596b478346a6df1ff1e3c78da9d01f16c9f73ce967407a9c0ece"
REBUILT_ZIP_SHA256 = "4f78ba072f5b458231ba8ba394e25bc9fc953e2bf288f28e30682a4e7a5a3a60"
PORTABLE_SHA256 = "ab26c7ea23496938e6e15e02f58eb8e6906db358acc2a9f24b7bdc28bee52d3f"
DEFAULT_ARCHIVE = ROOT / "tests/fixtures/simlox_pairing/a01-a02-handoff-519b209.zip"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode())


def load_handoff(path: Path = DEFAULT_ARCHIVE) -> dict:
    """Verify external pins BEFORE executing the frozen portable validator.

    The archive is a content snapshot rebuilt from the exact GitHub dependency,
    not the original delivered ZIP. Windows raw evidence is neither fetched nor
    executed here. A matching payload hash is integrity, not native reacceptance.
    """
    raw = path.read_bytes()
    if sha256(raw) != REBUILT_ZIP_SHA256:
        raise ValueError("rebuilt archive differs from the externally pinned snapshot")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
            for name in names
        ):
            raise ValueError("unsafe or duplicate archive member")
        manifest_bytes = archive.read("manifest.json")
        if sha256(manifest_bytes) != MANIFEST_SHA256:
            raise ValueError("external manifest fingerprint mismatch")
        manifest = json.loads(manifest_bytes)
        payload = manifest["payload_files"]
        if set(names) != set(payload) | {"manifest.json"}:
            raise ValueError("archive membership mismatch")
        files = {name: archive.read(name) for name in payload}
        for name, spec in payload.items():
            if sha256(files[name]) != spec["sha256"] or len(files[name]) != spec["bytes"]:
                raise ValueError(f"payload fingerprint mismatch: {name}")
        if sha256(files["portable.py"]) != PORTABLE_SHA256:
            raise ValueError("portable verifier external pin mismatch")
    # Only this exact hash-pinned dependency script is allowed to execute.
    with tempfile.TemporaryDirectory(prefix="a01-a02-portable-") as directory:
        script = Path(directory) / "portable.py"
        script.write_bytes(files["portable.py"])
        verifier = runpy.run_path(str(script))["verify_package"]
        receipt = verifier(path, MANIFEST_SHA256)
    return {
        "manifest": manifest,
        "expected": json.loads(files["expected-observations.json"]),
        "report_template": json.loads(files["consumer-report-template.json"]),
        "contracts": {case: json.loads(files[f"cases/{case}/contract.json"])
                      for case in ("A01", "A02")},
        "verification": {
            **receipt,
            "dependency_commit": DEPENDENCY,
            "dependency_repository": "https://github.com/jihegao/sim_engine_compiler.git",
            "delivered_zip_sha256": DELIVERED_ZIP_SHA256,
            "delivered_zip_verified": False,
            "rebuilt_zip_matches_delivered_bytes": False,
            "archive_boundary": "rebuilt_snapshot_external_manifest_and_payload_verified",
            "native_raw_evidence_rechecked_here": False,
        },
    }


def source_identity() -> dict:
    """Fingerprint actual imported engine sources, separately from consumer code."""
    from sim_engine_compiler.reference import SimpyReferenceRuntime

    expected_runtime = ROOT / "src/sim_engine_compiler/reference/simpy_runtime.py"
    if Path(inspect.getfile(SimpyReferenceRuntime)).resolve() != expected_runtime.resolve():
        raise ValueError("imported runtime is not this checkout; set PYTHONPATH=src")
    files = sorted((ROOT / "src/sim_engine_compiler").rglob("*.py"))
    files.append(ROOT / "pyproject.toml")
    sources = {str(path.relative_to(ROOT)): sha256(path.read_bytes()) for path in files}
    if json_digest(sources) != BASELINE_BUILD_SHA256:
        raise ValueError("engine sources differ from the frozen main baseline")
    consumer = {str(path.relative_to(ROOT)): sha256(path.read_bytes())
                for path in sorted(Path(__file__).parent.glob("*.py"))}
    return {
        "commit": BASELINE,
        "commit_scope": "engine_source_baseline_not_consumer_PR_head",
        "build_kind": "independent_python_reference_source_execution",
        "build_fingerprint": json_digest(sources),
        "source_files": sources,
        "consumer_source_fingerprint": json_digest(consumer),
        "consumer_source_files": consumer,
        "python": platform.python_version(),
        "simpy": version("simpy"),
        "identity_pr20_dependency": None,
    }
