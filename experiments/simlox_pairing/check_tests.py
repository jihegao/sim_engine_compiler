"""Fail closed unless every pairing test module actually runs without skips."""

from __future__ import annotations

import json
import unittest

MODULES = (
    "tests.conformance.test_simlox_pairing_canonical",
    "tests.conformance.test_simlox_pairing_observations",
    "tests.conformance.test_simlox_pairing_provenance",
    "tests.conformance.test_simlox_pairing_runner",
)


def required_suite() -> tuple[unittest.TestSuite, dict[str, int]]:
    suite = unittest.TestSuite()
    counts = {}
    for module in MODULES:
        loaded = unittest.defaultTestLoader.loadTestsFromName(module)
        counts[module] = loaded.countTestCases()
        if not counts[module]:
            raise ValueError(f"required module has no discoverable unittest cases: {module}")
        suite.addTests(loaded)
    return suite, counts


def main() -> int:
    suite, counts = required_suite()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    accepted = (result.wasSuccessful() and not result.skipped
                and not result.expectedFailures and not result.unexpectedSuccesses
                and result.testsRun == sum(counts.values()))
    print(json.dumps({"schema": "a01-a02-test-execution/v1",
                      "collected": sum(counts.values()), "executed": result.testsRun,
                      "module_counts": counts, "skipped": len(result.skipped),
                      "failures": len(result.failures), "errors": len(result.errors),
                      "status": "passed" if accepted else "failed"}, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
