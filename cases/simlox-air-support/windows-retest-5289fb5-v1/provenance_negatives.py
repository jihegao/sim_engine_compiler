"""Independent, disposable Windows file mutations against PR22 source policy.

Usage: python provenance_negatives.py PR22_CHECKOUT DISPATCH OUTPUT_JSON
The real PR22 checkout and native SIMLOX inputs remain read-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE = "595cb5eee9987324b19a8c3566f201f937e05f15"
SOURCE = Path("src/sim_engine_compiler/reference/simpy_runtime.py")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def check_case(root: Path, name: str, action, verifier) -> dict:
    git(root, "reset", "--hard", "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe")
    target = root / SOURCE
    before = digest(target)
    detail = action(root, target)
    after = digest(target)
    try:
        verifier(root, BASELINE)
    except Exception as error:
        result = {"name": name, "status": "rejected", "exception_type": type(error).__name__,
                  "exception": str(error), "source_path": str(target),
                  "source_sha256_before": before, "source_sha256_after": after,
                  "mutation": detail, "checkout_head": git(root, "rev-parse", "HEAD")}
        return result
    raise AssertionError(f"negative control unexpectedly accepted: {name}")


def main() -> None:
    checkout, dispatch, target = map(Path, sys.argv[1:4])
    assert not target.exists()
    sys.path.insert(0, str(checkout))
    sys.path.insert(0, str(checkout / "src"))
    from experiments.simlox_pairing.provenance import _verified_engine_sources

    results = []
    with tempfile.TemporaryDirectory(prefix="pr22-windows-negative-", dir=dispatch) as temporary:
        root = Path(temporary) / "repo"
        subprocess.run(["git", "clone", "--quiet", "--no-checkout", "--no-hardlinks",
                        str(checkout), str(root)], check=True)
        git(root, "config", "--local", "core.autocrlf", "false")
        git(root, "checkout", "--detach", "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe")
        assert _verified_engine_sources(root, BASELINE)["build_fingerprint"] == \
            "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1"

        def rewrite(data: bytes):
            return lambda _root, path: (path.write_bytes(data), {"mutated_file_sha256": digest(path)})[1]

        blob = (root / SOURCE).read_bytes()
        assert b"\r" not in blob and blob.count(b"\n") > 2
        results.append(check_case(root, "dirty_content", rewrite(blob + b"# dirty edit\n"),
                                  _verified_engine_sources))
        results.append(check_case(root, "mixed_lf_crlf", rewrite(blob.replace(b"\n", b"\r\n", 1)),
                                  _verified_engine_sources))
        results.append(check_case(root, "bare_cr", rewrite(blob.replace(b"\n", b"\r", 1)),
                                  _verified_engine_sources))

        def add(root: Path, _target: Path):
            extra = root / "src/sim_engine_compiler/unexpected_source.py"
            extra.write_bytes(b"unexpected = True\n")
            return {"added_path": str(extra), "added_sha256": digest(extra)}

        results.append(check_case(root, "added_engine_python", add, _verified_engine_sources))
        # Remove the untracked file explicitly; git reset does not clean untracked files.
        (root / "src/sim_engine_compiler/unexpected_source.py").unlink()

        def missing(_root: Path, path: Path):
            path.unlink()
            return {"removed": str(path)}

        results.append(check_case(root, "missing_engine_python", missing,
                                  _verified_engine_sources))
        results.append(check_case(root, "missing_baseline_object",
                                  lambda _root, _target: {"requested_revision": "0" * 40},
                                  lambda candidate, _revision:
                                  _verified_engine_sources(candidate, "0" * 40)))

        # A fresh real repository has a valid HEAD and the current 26 engine
        # source files, but deliberately has no object for the fixed baseline.
        # This is stronger than requesting an all-zero revision from the full
        # history checkout: HEAD must not silently replace the missing ID.
        isolated = Path(temporary) / "valid-head-without-fixed-baseline"
        isolated.mkdir()
        subprocess.run(["git", "init", "--quiet", str(isolated)], check=True)
        git(isolated, "config", "--local", "core.autocrlf", "false")
        shutil.copytree(checkout / "src/sim_engine_compiler",
                        isolated / "src/sim_engine_compiler",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(checkout / "pyproject.toml", isolated / "pyproject.toml")
        sources = [isolated / "pyproject.toml"] + sorted(
            (isolated / "src/sim_engine_compiler").rglob("*.py"))
        assert len(sources) == 26
        source_hashes = {
            path.relative_to(isolated).as_posix(): digest(path) for path in sources
        }
        assert source_hashes == {
            path.relative_to(isolated).as_posix(): digest(checkout / path.relative_to(isolated))
            for path in sources
        }
        git(isolated, "add", "pyproject.toml", "src/sim_engine_compiler")
        git(isolated, "-c", "user.name=Pairing Review", "-c",
            "user.email=pairing-review@example.invalid", "commit", "-m",
            "disposable current engine source")
        isolated_head = git(isolated, "rev-parse", "HEAD")
        assert git(isolated, "cat-file", "-t", isolated_head) == "commit"
        missing = subprocess.run(["git", "-C", str(isolated), "cat-file", "-e",
                                  BASELINE + "^{commit}"], capture_output=True)
        assert missing.returncode != 0
        try:
            _verified_engine_sources(isolated, BASELINE)
        except Exception as error:
            assert "frozen baseline Git object unavailable" in str(error)
            results.append({
                "name": "actual_fixed_baseline_absent_with_valid_head",
                "status": "rejected", "exception_type": type(error).__name__,
                "exception": str(error), "checkout_head": isolated_head,
                "requested_baseline": BASELINE,
                "baseline_cat_file_exit_code": missing.returncode,
                "source_file_count": len(sources),
                "source_file_sha256": source_hashes,
            })
        else:
            raise AssertionError("missing actual fixed baseline silently used HEAD")

        git(root, "reset", "--hard", "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe")
        source = root / SOURCE
        baseline_hash = digest(source)
        source.write_bytes(source.read_bytes() + b"# alternate valid revision\n")
        git(root, "add", str(SOURCE).replace("\\", "/"))
        git(root, "-c", "user.name=Pairing Review", "-c",
            "user.email=pairing-review@example.invalid", "commit", "-m", "alternate valid revision")
        alternate = git(root, "rev-parse", "HEAD")
        assert alternate != BASELINE
        assert git(root, "cat-file", "-t", alternate) == "commit"
        alternate_identity = _verified_engine_sources(root, alternate)
        assert alternate_identity["build_fingerprint"] != \
            "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1"
        try:
            _verified_engine_sources(root, BASELINE)
        except Exception as error:
            wrong = {"name": "valid_wrong_revision_not_substituted_for_baseline",
                     "status": "rejected", "exception_type": type(error).__name__,
                     "exception": str(error), "checkout_head": alternate,
                     "requested_baseline": BASELINE,
                     "baseline_file_sha256": baseline_hash,
                     "alternate_file_sha256": digest(source),
                     "alternate_build_fingerprint": alternate_identity["build_fingerprint"]}
        else:
            raise AssertionError("valid wrong revision was silently accepted as baseline")
        results.append(wrong)

        outside = Path(temporary) / "outside"
        external = outside / "sim_engine_compiler/reference"
        external.mkdir(parents=True)
        (outside / "sim_engine_compiler/__init__.py").write_bytes(b"")
        (external / "__init__.py").write_bytes(b"class SimpyReferenceRuntime: pass\n")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(outside) + os.pathsep + str(checkout)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [sys.executable, "-c",
                   "from experiments.simlox_pairing.provenance import source_identity; source_identity()"]
        process = subprocess.run(command, cwd=checkout, env=env, capture_output=True)
        assert process.returncode != 0 and b"imported runtime is not this checkout" in process.stderr
        results.append({"name": "outside_checkout_runtime_import", "status": "rejected",
                        "exit_code": process.returncode, "command": command,
                        "cwd": str(checkout), "external_path": str(external / "__init__.py"),
                        "external_sha256": digest(external / "__init__.py"),
                        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
                        "stderr_excerpt": process.stderr.decode("utf-8", errors="replace")[-900:]})

    expected = {
        "dirty_content": "differs from frozen baseline",
        "mixed_lf_crlf": "differs from frozen baseline",
        "bare_cr": "differs from frozen baseline",
        "added_engine_python": "membership differs",
        "missing_engine_python": "membership differs",
        "missing_baseline_object": "frozen baseline Git object unavailable",
        "actual_fixed_baseline_absent_with_valid_head":
            "frozen baseline Git object unavailable",
        "valid_wrong_revision_not_substituted_for_baseline": "differs from frozen baseline",
    }
    for item in results:
        if item["name"] in expected:
            assert expected[item["name"]] in item["exception"], item
    report = {"schema": "simlox-pr22-windows-negative-controls/v1",
              "pr22_head": "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe",
              "baseline": BASELINE,
              "status": "all_rejected_as_required",
              "controls": results}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "count": len(results),
                      "output": str(target)}))


if __name__ == "__main__":
    main()
