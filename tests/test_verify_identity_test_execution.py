from __future__ import annotations

from pathlib import Path

from scripts.verify_identity_test_execution import main, verify


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_matching_collection_and_junit_report_exact_counts(tmp_path: Path) -> None:
    collection = _write(
        tmp_path / "collection.txt",
        "tests/conformance/test_identity_cli.py::test_cli[a]\n"
        "tests/conformance/test_identity_runs.py::RunTests::test_run\n"
        "2 tests collected in 0.01s\n",
    )
    junit = _write(
        tmp_path / "junit.xml",
        '<testsuites><testsuite tests="2">'
        '<testcase classname="tests.conformance.test_identity_cli" name="test_cli[a]" />'
        '<testcase classname="tests.conformance.test_identity_runs.RunTests" '
        'name="test_run" />'
        "</testsuite></testsuites>",
    )

    evidence = verify(
        collection,
        junit,
        ["tests/conformance/test_identity_cli.py", "tests/conformance/test_identity_runs.py"],
    )

    assert evidence["status"] == "passed"
    assert evidence["collected"] == evidence["recorded"] == evidence["passed"] == 2
    assert evidence["executed"] == 2
    assert evidence["required_modules"] == {
        "tests/conformance/test_identity_cli.py": 1,
        "tests/conformance/test_identity_runs.py": 1,
    }


def test_missing_or_unexecuted_required_case_fails_closed(tmp_path: Path) -> None:
    collection = _write(
        tmp_path / "collection.txt",
        "tests/conformance/test_identity_cli.py::test_one\n"
        "tests/conformance/test_identity_cli.py::test_two\n",
    )
    junit = _write(
        tmp_path / "junit.xml",
        '<testsuites><testsuite tests="1">'
        '<testcase classname="tests.conformance.test_identity_cli" name="test_one" />'
        "</testsuite></testsuites>",
    )

    evidence = verify(
        collection,
        junit,
        ["tests/conformance/test_identity_cli.py", "tests/conformance/test_identity_missing.py"],
    )

    assert evidence["status"] == "failed"
    assert evidence["collected"] == 2
    assert evidence["recorded"] == 1
    assert any("missing from JUnit" in item for item in evidence["diagnostics"])
    assert any("required module did not execute" in item for item in evidence["diagnostics"])


def test_required_module_skip_fails_closed(tmp_path: Path) -> None:
    collection = _write(
        tmp_path / "collection.txt",
        "tests/conformance/test_identity_cli.py::test_one\n",
    )
    junit = _write(
        tmp_path / "junit.xml",
        '<testsuites><testsuite tests="1" skipped="1">'
        '<testcase classname="tests.conformance.test_identity_cli" name="test_one">'
        '<skipped message="not available" />'
        "</testcase></testsuite></testsuites>",
    )

    evidence = verify(
        collection,
        junit,
        ["tests/conformance/test_identity_cli.py"],
    )

    assert evidence["status"] == "failed"
    assert evidence["executed"] == 0
    assert evidence["skipped"] == 1
    assert any("nonpassing tests" in item for item in evidence["diagnostics"])


def test_failure_outside_required_modules_still_fails_closed(tmp_path: Path) -> None:
    collection = _write(
        tmp_path / "collection.txt",
        "tests/test_unrelated.py::test_failure\n",
    )
    junit = _write(
        tmp_path / "junit.xml",
        '<testsuites><testsuite tests="1" failures="1">'
        '<testcase classname="tests.test_unrelated" name="test_failure">'
        '<failure message="broken" />'
        "</testcase></testsuite></testsuites>",
    )

    evidence = verify(collection, junit, [])

    assert evidence["status"] == "failed"
    assert evidence["failures"] == 1
    assert evidence["executed"] == 1
    assert any("nonpassing execution results" in item for item in evidence["diagnostics"])


def test_cli_rejects_empty_collection_evidence(tmp_path: Path) -> None:
    collection = _write(tmp_path / "collection.txt", "no tests collected\n")
    junit = _write(tmp_path / "junit.xml", "<testsuites />")

    assert main(["--collection", str(collection), "--junit", str(junit)]) == 2
