"""Externally pinned source handoff and executable-source identities."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
import runpy
import subprocess
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path, PurePath, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "595cb5eee9987324b19a8c3566f201f937e05f15"
BASELINE_BUILD_SHA256 = (
    "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1"
)
DEPENDENCY = "519b2094c3be355399bc101cdcfe30d456cbb47b"
MANIFEST_SHA256 = "0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987"
DELIVERED_ZIP_SHA256 = (
    "fe5555954cc6596b478346a6df1ff1e3c78da9d01f16c9f73ce967407a9c0ece"
)
REBUILT_ZIP_SHA256 = "4f78ba072f5b458231ba8ba394e25bc9fc953e2bf288f28e30682a4e7a5a3a60"
PORTABLE_SHA256 = "ab26c7ea23496938e6e15e02f58eb8e6906db358acc2a9f24b7bdc28bee52d3f"
DEFAULT_ARCHIVE = ROOT / "tests/fixtures/simlox_pairing/a01-a02-handoff-519b209.zip"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    )


def _canonical_path_key(relative: PurePath) -> str:
    """Return a platform-independent repository key from native path parts."""
    return PurePosixPath(*relative.parts).as_posix()


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        detail = (
            error.stderr.decode(errors="replace").strip()
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        raise ValueError(
            "frozen baseline Git object unavailable; fetch the exact baseline commit: "
            f"{detail}"
        ) from error


def _baseline_source_blobs(root: Path, revision: str) -> dict[str, tuple[str, bytes]]:
    listing = _git(
        root,
        "ls-tree",
        "-r",
        revision,
        "--",
        "src/sim_engine_compiler",
        "pyproject.toml",
    ).decode()
    result: dict[str, tuple[str, bytes]] = {}
    for line in listing.splitlines():
        metadata, name = line.split("\t", 1)
        _, object_type, object_id = metadata.split()
        key = PurePosixPath(name).as_posix()
        if object_type != "blob" or (
            key != "pyproject.toml" and not key.endswith(".py")
        ):
            continue
        result[key] = (object_id, _git(root, "cat-file", "blob", object_id))
    if "pyproject.toml" not in result or not any(
        key.startswith("src/sim_engine_compiler/") for key in result
    ):
        raise ValueError(
            "frozen baseline does not contain the required engine source tree"
        )
    return dict(sorted(result.items()))


def _executed_byte_mode(blob: bytes, executed: bytes, key: str) -> str:
    """Accept exact bytes or one strict whole-file LF-to-CRLF checkout transform."""
    if executed == blob:
        return "exact_git_blob_bytes"
    try:
        blob.decode("utf-8")
        executed.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"executed source is not UTF-8 text: {key}") from error
    if b"\r" not in blob and executed == blob.replace(b"\n", b"\r\n"):
        return "controlled_whole_file_lf_to_crlf_checkout"
    raise ValueError(f"executed source differs from frozen baseline Git blob: {key}")


def _verified_engine_sources(root: Path, revision: str) -> dict:
    blobs = _baseline_source_blobs(root, revision)
    actual_paths = sorted((root / "src/sim_engine_compiler").rglob("*.py"))
    actual_paths.append(root / "pyproject.toml")
    actual = {
        _canonical_path_key(path.relative_to(root)): path for path in actual_paths
    }
    expected_keys = set(blobs)
    actual_keys = set(actual)
    if actual_keys != expected_keys:
        added = sorted(actual_keys - expected_keys)
        missing = sorted(expected_keys - actual_keys)
        raise ValueError(
            f"executed engine source membership differs from baseline; added={added}, missing={missing}"
        )
    canonical_hashes: dict[str, str] = {}
    blob_oids: dict[str, str] = {}
    executed_hashes: dict[str, str] = {}
    modes: dict[str, str] = {}
    for key, (object_id, blob) in blobs.items():
        executed = actual[key].read_bytes()
        modes[key] = _executed_byte_mode(blob, executed, key)
        canonical_hashes[key] = sha256(blob)
        blob_oids[key] = object_id
        executed_hashes[key] = sha256(executed)
    return {
        "source_files": canonical_hashes,
        "source_git_blob_oids": blob_oids,
        "executed_source_files": executed_hashes,
        "executed_source_modes": modes,
        "build_fingerprint": json_digest(canonical_hashes),
        "executed_source_fingerprint": json_digest(executed_hashes),
    }


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
            if (
                sha256(files[name]) != spec["sha256"]
                or len(files[name]) != spec["bytes"]
            ):
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
        "contracts": {
            case: json.loads(files[f"cases/{case}/contract.json"])
            for case in ("A01", "A02")
        },
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
    """Bind frozen Git blobs to the actual imported and executed source bytes."""
    from sim_engine_compiler.reference import SimpyReferenceRuntime

    expected_runtime = ROOT / "src/sim_engine_compiler/reference/simpy_runtime.py"
    if (
        Path(inspect.getfile(SimpyReferenceRuntime)).resolve()
        != expected_runtime.resolve()
    ):
        raise ValueError("imported runtime is not this checkout; set PYTHONPATH=src")
    engine = _verified_engine_sources(ROOT, BASELINE)
    if engine["build_fingerprint"] != BASELINE_BUILD_SHA256:
        raise ValueError("engine sources differ from the frozen main baseline")
    consumer = {
        _canonical_path_key(path.relative_to(ROOT)): sha256(path.read_bytes())
        for path in sorted(Path(__file__).parent.glob("*.py"))
    }
    return {
        "commit": BASELINE,
        "commit_scope": "engine_source_baseline_not_consumer_PR_head",
        "build_kind": "independent_python_reference_source_execution",
        **engine,
        "source_byte_policy": "git-blob-or-strict-whole-file-lf-to-crlf/v1",
        "consumer_source_fingerprint": json_digest(consumer),
        "consumer_source_files": consumer,
        "python": platform.python_version(),
        "simpy": version("simpy"),
        "identity_pr20_dependency": None,
    }
