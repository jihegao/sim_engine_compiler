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

# PRs #20, #23, #24, Issue #29, the reviewed #542 additions, and the
# domain-profile queue modules are explicit checkout sources. Their pinned
# bytes and the declared engine delta stay separate from the frozen pairing
# baseline and do not change its historic Git blob fingerprint.
DECLARED_NONBASELINE_SOURCE_CONTRACT = "simlox-pairing-checkout-additions/v6"
DECLARED_MODIFIED_BASELINE_SOURCE_CONTRACT = "simlox-pairing-declared-engine-delta/v1"
DECLARED_MODIFIED_BASELINE_SOURCE_SHA256 = {
    "src/sim_engine_compiler/ir/layers.py": (
        "4fb0c06cfad201a62f3e000f535b52affec1c583cc8adfa45fdc8793b6388749"
    ),
    "src/sim_engine_compiler/reference/abm_runtime.py": (
        "46ef80ad188c39bc8d733378b143a29d46c0bba67eda63904067070bb352e10f"
    ),
}
DECLARED_NONBASELINE_SOURCE_SHA256 = {
    "src/sim_engine_compiler/cli.py": (
        "b8b2dc25e20d941a7259b08eda2c022dbb965dc43e1db61ba9a06a85a5e7af21"
    ),
    "src/sim_engine_compiler/compiler/bounded_layout.py": (
        "d25d5954a4530d6e4f9fb08ee19f9041762be2dea80045a916512788afa7cc11"
    ),
    "src/sim_engine_compiler/domains/aircraft_support/bounded.py": (
        "09ed36be1cabc303a5d8f3d03c86f6674e96160475c8c09c06b23693fe26ff47"
    ),
    "src/sim_engine_compiler/domains/aircraft_support/bounded_runtime.py": (
        "c2d89dd900d0b531832876078a5bf96c0a9d39de83397333032eea45b266ba68"
    ),
    "src/sim_engine_compiler/domains/aircraft_support/pack.py": (
        "79604414106d3ac03f60fd7e99475af00ebfb81c00eacffa49837e7d4d42209b"
    ),
    "src/sim_engine_compiler/domains/multi_server_queue/__init__.py": (
        "11ba6f23c0a7515239b9b8b7ac818565abf54028194509ad8d201e7df94e58d4"
    ),
    "src/sim_engine_compiler/domains/multi_server_queue/model.py": (
        "bb35796e5ec0ef7776cfa1caeca9db9a2214c27e7e5945e517010b8b9361128d"
    ),
    "src/sim_engine_compiler/domains/multi_server_queue/pack.py": (
        "c5919f5ff97235bd67586bbf099a596457541a168889443e709a250697327fd5"
    ),
    "src/sim_engine_compiler/domains/multi_server_queue/runtime.py": (
        "979be910cff9366b0605229a2c2c380d00b3ac6ee892bb4a8d2a56a769a03685"
    ),
    "src/sim_engine_compiler/domains/multi_server_queue/trace.py": (
        "1a8e0203a95c5b49ef4189f51735568fbb7551788f617c758002fb968d2aff51"
    ),
    "src/sim_engine_compiler/domains/profiles.py": (
        "3ef478edbc39f7eeaf80607339b0bfbd41f2aff0cec358bdaa58a768ef8440d9"
    ),
    "src/sim_engine_compiler/examples/__init__.py": (
        "eed06b92b7f3972187c4ad316563b05c0c3c848ec60aba6c140d150c944019fe"
    ),
    "src/sim_engine_compiler/identity/__init__.py": (
        "3cb31c00457b10ac369f0f059df6d536a97896492c3bed51ee4469e08e080c38"
    ),
    "src/sim_engine_compiler/identity/__main__.py": (
        "e0df441b01f212591e6658e3f6513548f3b0246962054ddb342d88a55e49be32"
    ),
    "src/sim_engine_compiler/identity/artifacts.py": (
        "07667396c189d6ba77c01e53c9d34012a4b973c641a9c3f9f89911d2fc08a555"
    ),
    "src/sim_engine_compiler/identity/common.py": (
        "759932aa37d96ac261dbfecae5b24858fc7483e7a7866bbf259166666daef1fd"
    ),
    "src/sim_engine_compiler/identity/runs.py": (
        "3b1a4c9a9ee0b98a88d539fbd14bd3467d604afb3bc101fe009df9ad089e69e0"
    ),
    "src/sim_engine_compiler/integrations/spare_mvp/bounded.py": (
        "32e5bba4fa1749dbd9dfd644539036fa9cd5aae2c650bb386e870e1a84658d78"
    ),
    "src/sim_engine_compiler/ir/bounded.py": (
        "363131a6018b337a3802e8cf29a3c28d5855fa9e43a92c208fe0816e855f295a"
    ),
    "src/sim_engine_compiler/product.py": (
        "186791fe16f5bd0e19263ff11b6ccff5a53de35d1b7b4583506a6d0da3fe6e6a"
    ),
    "src/sim_engine_compiler/reference/event_calendar.py": (
        "f2dc90a52c0425be44ce270fcded4bdd49a27a4fe2d0af546f61a943e77efc3d"
    ),
    "src/sim_engine_compiler/review/__init__.py": (
        "aa6fbb2a420bbae2f93bbecd7e9769411348bab559f5b38b4d1ac314c6f61b05"
    ),
    "src/sim_engine_compiler/review/__main__.py": (
        "69b9b14a5f5ac62ea3e1d721c4fc1afc1ed2ab5ed6edb670b307a6e64a3593a4"
    ),
    "src/sim_engine_compiler/review/exporter.py": (
        "698615a85153e89bf2c9da2eefeafdc8bcf99a3b167ae43f0fcd92618a784b03"
    ),
    "src/sim_engine_compiler/review/views.py": (
        "28735cbb890050b359181c164bb2724e08e8b9479b0f14ce473483ed18190256"
    ),
    "src/sim_engine_compiler/trace_query/__init__.py": (
        "c0e6ccf516db95362ef5c37a0c22cec3eee5bbbd27fd908823c2156c2463fbfc"
    ),
    "src/sim_engine_compiler/trace_query/__main__.py": (
        "252556632f749f07d5c66e5b7396dfcc7ea171d00e55eb62dc85e4be89f52e33"
    ),
    "src/sim_engine_compiler/trace_query/facts.py": (
        "1117d82de0879dc533f4bc8366efd69ecc7732ece6cdde4efa82767bc0f75af3"
    ),
    "src/sim_engine_compiler/trace_query/query.py": (
        "1e6514af510b5cec140f2df1ae11aba3ffe8bc956bd2b4b7d2b520ebac51963d"
    ),
}
DECLARED_BASELINE_OVERRIDE_SHA256 = {
    "pyproject.toml": "eaff5fe0c87adcbf3e676e7047f61ef2bacf780c8cfb3b0029ebd46ea52a673c",
    "src/sim_engine_compiler/__init__.py": (
        "73fccdde6a98b5b561ec7017725f87df4618c4e07822d922a39f2208eb606125"
    ),
}


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
        ).encode("utf-8")
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
            error.stderr.decode("utf-8", errors="replace").strip()
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
    ).decode("utf-8")
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


def _declared_digest_mode(executed: bytes, expected_sha256: str, key: str) -> str:
    """Verify a content-pinned checkout addition with the baseline newline policy."""
    if sha256(executed) == expected_sha256:
        return "exact_declared_bytes"
    if b"\r\n" in executed:
        remainder = executed.replace(b"\r\n", b"")
        normalized = executed.replace(b"\r\n", b"\n")
        if (
            b"\r" not in remainder
            and b"\n" not in remainder
            and sha256(normalized) == expected_sha256
        ):
            return "controlled_whole_file_lf_to_crlf_checkout"
    raise ValueError(f"declared source differs from pinned content: {key}")


def _verified_engine_sources(
    root: Path,
    revision: str,
    *,
    declared_nonbaseline_sources: dict[str, str] | None = None,
    declared_baseline_overrides: dict[str, str] | None = None,
    declared_modified_baseline_sources: dict[str, str] | None = None,
) -> dict:
    blobs = _baseline_source_blobs(root, revision)
    declared = dict(sorted((declared_nonbaseline_sources or {}).items()))
    overrides = dict(sorted((declared_baseline_overrides or {}).items()))
    modified = dict(sorted((declared_modified_baseline_sources or {}).items()))
    overlap = set(blobs) & set(declared)
    if overlap:
        raise ValueError(
            "declared nonbaseline sources overlap frozen baseline: "
            f"{sorted(overlap)}"
        )
    unknown_overrides = set(overrides) - set(blobs)
    if unknown_overrides:
        raise ValueError(f"declared baseline overrides are not baseline blobs: {sorted(unknown_overrides)}")
    missing_modifications = sorted(set(modified) - set(blobs))
    if missing_modifications:
        raise ValueError(
            "declared modified source is absent from frozen baseline: "
            f"{missing_modifications}"
        )
    if set(modified) & set(overrides):
        raise ValueError("modified baseline sources overlap baseline overrides")
    actual_paths = sorted((root / "src/sim_engine_compiler").rglob("*.py"))
    actual_paths.append(root / "pyproject.toml")
    actual = {
        _canonical_path_key(path.relative_to(root)): path for path in actual_paths
    }
    expected_keys = set(blobs) | set(declared)
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
        if key in modified:
            if len(modified[key]) != 64:
                raise ValueError(f"invalid declared modified source digest: {key}")
            modes[key] = _declared_digest_mode(executed, modified[key], key)
        elif key in overrides:
            modes[key] = "declared_postbaseline_" + _declared_digest_mode(executed, overrides[key], key)
        else:
            modes[key] = _executed_byte_mode(blob, executed, key)
        canonical_hashes[key] = sha256(blob)
        blob_oids[key] = object_id
        executed_hashes[key] = sha256(executed)
    declared_executed_hashes: dict[str, str] = {}
    declared_modes: dict[str, str] = {}
    for key, expected_sha256 in declared.items():
        if len(expected_sha256) != 64:
            raise ValueError(f"invalid declared nonbaseline source digest: {key}")
        executed = actual[key].read_bytes()
        declared_modes[key] = _declared_digest_mode(executed, expected_sha256, key)
        declared_executed_hashes[key] = sha256(executed)
    return {
        "source_files": canonical_hashes,
        "source_git_blob_oids": blob_oids,
        "executed_source_files": executed_hashes,
        "executed_source_modes": modes,
        "build_fingerprint": json_digest(canonical_hashes),
        "executed_source_fingerprint": json_digest(executed_hashes),
        "declared_nonbaseline_source_files": declared,
        "declared_nonbaseline_executed_source_files": declared_executed_hashes,
        "declared_nonbaseline_source_modes": declared_modes,
        "declared_baseline_overrides": overrides,
        "declared_modified_baseline_source_files": modified,
        "declared_modified_baseline_source_contract": (
            DECLARED_MODIFIED_BASELINE_SOURCE_CONTRACT
        ),
        "checkout_source_membership_fingerprint": json_digest(
            {**canonical_hashes, **declared, **overrides, **modified}
        ),
        "declared_nonbaseline_source_contract": (
            DECLARED_NONBASELINE_SOURCE_CONTRACT
        ),
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
        manifest = json.loads(manifest_bytes.decode("utf-8"))
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
        "expected": json.loads(files["expected-observations.json"].decode("utf-8")),
        "report_template": json.loads(
            files["consumer-report-template.json"].decode("utf-8")
        ),
        "contracts": {
            case: json.loads(files[f"cases/{case}/contract.json"].decode("utf-8"))
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
    engine = _verified_engine_sources(
        ROOT,
        BASELINE,
        declared_nonbaseline_sources=DECLARED_NONBASELINE_SOURCE_SHA256,
        declared_baseline_overrides=DECLARED_BASELINE_OVERRIDE_SHA256,
        declared_modified_baseline_sources=DECLARED_MODIFIED_BASELINE_SOURCE_SHA256,
    )
    if engine["build_fingerprint"] != BASELINE_BUILD_SHA256:
        raise ValueError("engine sources differ from the frozen main baseline")
    consumer = {
        _canonical_path_key(path.relative_to(ROOT)): sha256(path.read_bytes())
        for path in sorted(Path(__file__).parent.glob("*.py"))
    }
    return {
        "commit": BASELINE,
        "commit_scope": "frozen_engine_source_baseline_with_declared_checkout_delta",
        "checkout_head": _git(ROOT, "rev-parse", "HEAD").decode("ascii").strip(),
        "build_kind": "independent_python_reference_source_execution",
        **engine,
        "source_byte_policy": "git-blob-or-explicit-digest-with-strict-whole-file-lf-to-crlf/v2",
        "consumer_source_fingerprint": json_digest(consumer),
        "consumer_source_files": consumer,
        "python": platform.python_version(),
        "simpy": version("simpy"),
        "identity_pr20_dependency": None,
    }
