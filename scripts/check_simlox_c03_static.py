"""Run only C03 preparation checks and emit a receipt for this exact PR head.

No native process, runtime, GUI, replay, performance test or historical test
receipt supplies acceptance here. The af2fffc prepared inputs remain immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "cases/simlox-air-support/c03-contract-prep-v1"
PREPARED_COMMIT = "af2fffc7e644b588f104918337c7b4112462801d"
MANIFEST_SHA = "85aad0240957622c96c000be0162aba8cc21083e558bf8223f51ecb6543e7007"
CONTRACT_SHA = "672bb85b26b405ef486e7b6933a0bf88bfe3136d07f2615fa75611c74f4dc45a"
TEST_MODULE = "tests.conformance.test_simlox_c03_contract_prep"
EXPECTED_TESTS = 12


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args]).decode("utf-8").strip()


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


class CountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_count = 0
        self.started_ids = []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.passed_count += 1
        super().addSuccess(test)


def counts(result, discovered):
    return {"discovered": discovered, "started": result.testsRun,
            "executed": result.testsRun - len(result.skipped),
            "passed": result.passed_count, "skipped": len(result.skipped),
            "failures": len(result.failures), "errors": len(result.errors),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses)}


def accept_counts(summary):
    expected = {"discovered": 12, "started": 12, "executed": 12, "passed": 12,
                "skipped": 0, "failures": 0, "errors": 0,
                "expected_failures": 0, "unexpected_successes": 0}
    require(summary == expected, f"C03 requires all 12 real tests without skips or expected failures: {summary}")


def validate_inputs():
    raw = (PREP / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA, "original af2fffc manifest bytes changed")
    require(sha((PREP / "contract.json").read_bytes()) == CONTRACT_SHA, "original contract bytes changed")
    manifest = json.loads(raw.decode("utf-8"))
    require(len(manifest["artifacts"]) == 15 and len(manifest["unchanged_dependencies"]) == 5,
            "original prepared artifact/dependency count changed")
    records = manifest["artifacts"] + manifest["unchanged_dependencies"]
    paths = [item["path"] for item in records]
    require(len(set(paths)) == 20, "duplicate manifest path")
    for item in records:
        path = (REPO / item["path"]).resolve()
        require(path.is_relative_to(REPO), "manifest path outside checkout")
        data = path.read_bytes()
        require(sha(data) == item["sha256"], f"manifest hash mismatch: {item['path']}")
        if "bytes" in item:
            require(len(data) == item["bytes"], f"manifest byte count mismatch: {item['path']}")
    return {"manifest_sha256": MANIFEST_SHA, "contract_sha256": CONTRACT_SHA,
            "prepared_artifacts_verified": 15, "dependencies_verified": 5,
            "inputs": [item for item in manifest["artifacts"] if "/inputs/" in item["path"]]}


def run(args):
    require(re.fullmatch(r"[0-9a-f]{40}", args.head) and re.fullmatch(r"[0-9a-f]{40}", args.base), "head/base must be full SHA")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "simlox-c03-static-ci/v1", "status": "failed",
              "prepared_source_commit": PREPARED_COMMIT,
              "pr_head": args.head, "pr_base": args.base, "pr_base_ref": args.base_ref,
              "python": platform.python_version(), "platform": platform.platform(),
              "scope": "static preparation only; native/GUI/engine behavior unverified",
              "native_execution": False, "runtime_execution": False,
              "github_run_id": os.getenv("GITHUB_RUN_ID"),
              "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
              "actions_sha": os.getenv("GITHUB_SHA"),
              "test_counts": {"discovered": 0, "started": 0, "executed": 0,
                              "passed": 0, "skipped": 0, "failures": 0,
                              "errors": 0, "expected_failures": 0,
                              "unexpected_successes": 0},
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "workflow_sha256": sha((REPO / ".github/workflows/simlox-c03-static.yml").read_bytes())}
    try:
        report["checkout_head"] = git("rev-parse", "HEAD")
        report["checkout_tree"] = git("rev-parse", "HEAD^{tree}")
        report["checkout_status"] = git("status", "--porcelain")
        require(report["checkout_head"] == args.head, "checkout is not the requested PR head")
        require(not report["checkout_status"], "static CI requires a clean exact-head checkout")
        git("cat-file", "-e", args.base + "^{commit}")
        subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", PREPARED_COMMIT, args.head], check=True)
        report["input_identity"] = validate_inputs()
        command = [sys.executable, str(PREP / "prepare.py"), "--check"]
        completed = subprocess.run(command, cwd=REPO, capture_output=True)
        (args.output / "prepare.stdout").write_bytes(completed.stdout)
        (args.output / "prepare.stderr").write_bytes(completed.stderr)
        report["prepare"] = {"command": command, "exit_code": completed.returncode,
                             "stdout_sha256": sha(completed.stdout), "stderr_sha256": sha(completed.stderr)}
        require(completed.returncode == 0, "prepare.py --check failed; see raw logs")
        report["prepare"]["result"] = json.loads(completed.stdout.decode("utf-8"))
        require(report["prepare"]["result"]["status"] == "prepared_static_validated_native_unverified", "unexpected preparation status")
        sys.path.insert(0, str(REPO))
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(TEST_MODULE)
        ids = list(test_ids(suite))
        report["discovered_test_ids"] = ids
        report["test_counts"]["discovered"] = len(ids)
        require(not loader.errors and len(ids) == EXPECTED_TESTS and len(set(ids)) == EXPECTED_TESTS, "expected exactly 12 distinct C03 tests")
        with (args.output / "conformance.log").open("w", encoding="utf-8") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=CountedResult).run(suite)
        report["test_counts"] = counts(result, len(ids))
        report["started_test_ids"] = result.started_ids
        require(result.started_ids == ids, "test execution did not cover discovered identities")
        accept_counts(report["test_counts"])
        report["conformance_log_sha256"] = sha((args.output / "conformance.log").read_bytes())
        require(not git("status", "--porcelain"), "test execution changed tracked/unignored source")
        report["status"] = "static_ci_passed_native_unverified"
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        (args.output / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0 if report["status"] == "static_ci_passed_native_unverified" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
