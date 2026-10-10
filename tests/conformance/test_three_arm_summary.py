from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.three_arm_v1 import driver, summarize


PHASES = (
    "plan_read_ns",
    "plan_parse_validate_ns",
    "fingerprint_ns",
    "run_state_initialization_ns",
    "single_sample_execution_ns",
    "single_sample_serialization_ns",
    "batch_execution_ns",
    "batch_serialization_ns",
    "batch_write_ns",
    "end_to_end_batch_ns",
)


def _write_json(path: Path, value: object) -> None:
    driver._write_json(path, value)


class ThreeArmSummaryTests(unittest.TestCase):
    def _fixture(self, directory: str) -> tuple[Path, dict, list[dict]]:
        root = Path(directory)
        cases = []
        for index, case_id in enumerate(driver.EXPECTED_CASE_IDS):
            cases.append(
                {
                    "case_id": case_id,
                    "observation_level": "full" if index == 10 else "summary",
                    "semantic_profile": "event-time-v2",
                    "plan_fingerprint": f"{index + 1:064x}",
                    "scan_plan": {
                        "path": str(root / f"{case_id}-scan.json"),
                        "bytes": 100 + index,
                        "work_policy": "stable-topological-serial",
                        "rng_profile": "legacy-sequential-v1",
                    },
                    "indexed_plan": {
                        "path": str(root / f"{case_id}-indexed.json"),
                        "bytes": 200 + index,
                        "work_policy": "stable-topological-serial",
                        "rng_profile": "legacy-sequential-v1",
                    },
                }
            )
        manifest = {
            "schema_version": driver.MANIFEST_SCHEMA,
            "cases": cases,
            "schedule": driver._schedule(cases),
            "protocol": {
                "seeds": list(driver.SEEDS),
                "worker_threads": driver.WORKER_THREADS,
                "warmups_per_process": driver.WARMUPS,
                "repeats": driver.REPEATS,
                "arm_rotations": [list(value) for value in driver.ARM_ROTATIONS],
                "cpuset": "0-7",
                "cell_timeout_seconds": driver.CELL_TIMEOUT_SECONDS,
                "postflight_reserve_seconds": driver.POSTFLIGHT_RESERVE_SECONDS,
                "minimum_cell_start_seconds": driver.MINIMUM_CELL_START_SECONDS,
                "window_deadline_seconds": driver.WINDOW_DEADLINE_SECONDS,
                "max_normalized_load": driver.MAX_NORMALIZED_LOAD,
            },
        }
        manifest_path = root / "manifest.json"
        _write_json(manifest_path, manifest)
        (root / "manifest.sha256").write_text(
            driver.sha256_file(manifest_path) + "\n", encoding="ascii"
        )

        records = []
        measures = {
            "scan": (100, 100, 1000),
            "cache": (95, 95, 1050),
            "candidates": (105, 99, 1000),
        }
        cases_by_id = {case["case_id"]: case for case in cases}
        for cell in manifest["schedule"]:
            case = cases_by_id[cell["case_id"]]
            plan = case["scan_plan"] if cell["arm"] == "scan" else case["indexed_plan"]
            batch_execution_ns, end_to_end_batch_ns, rss = measures[cell["arm"]]
            phases = {phase: 1 for phase in PHASES}
            phases["batch_execution_ns"] = batch_execution_ns
            phases["end_to_end_batch_ns"] = end_to_end_batch_ns
            samples_sha256 = f"{cell['ordinal'] + 1:064x}"
            report = {
                "schema_version": driver.REPORT_SCHEMA,
                "plan_path": plan["path"],
                "plan_bytes": plan["bytes"],
                "plan_fingerprint": case["plan_fingerprint"],
                "semantic_profile": case["semantic_profile"],
                "work_policy": plan["work_policy"],
                "rng_profile": plan["rng_profile"],
                "seeds": list(driver.SEEDS),
                "worker_threads": driver.WORKER_THREADS,
                "warmups": driver.WARMUPS,
                "repeats": 1,
                "until": None,
                "observation_level": cell["observation_level"],
                "dependency_dispatch": cell["arm"] == "candidates",
                "rustc": "rustc 1.90.0 (synthetic)",
                "records": [
                    {
                        "repeat": 0,
                        "sample_indexes": [0, 1, 2],
                        "seeds": list(driver.SEEDS),
                        "samples_sha256": samples_sha256,
                        "batch_result_sha256": "a" * 64,
                        "single_result_bytes": 10,
                        "batch_result_bytes": 30,
                        "phases": phases,
                    }
                ],
            }
            cell_dir = root / "measurement" / f"cell-{cell['ordinal']:03d}"
            report_path = cell_dir / "stage-c-report.json"
            _write_json(report_path, report)
            time_path = cell_dir / "gnu-time.txt"
            time_path.write_text(
                f"Maximum resident set size (kbytes): {rss}\n", encoding="utf-8"
            )
            record = {
                "cell": cell,
                "status": "complete",
                "execution": {"wall_ns": 1000 + cell["ordinal"]},
                "stage_c_report_sha256": driver.sha256_file(report_path),
                "samples_sha256": samples_sha256,
                "gnu_time": driver.parse_gnu_time(time_path.read_text(encoding="utf-8")),
                "gnu_time_sha256": driver.sha256_file(time_path),
            }
            _write_json(cell_dir / "record.json", record)
            records.append(record)
        _write_json(
            root / "state.json",
            {
                "schema_version": driver.STATE_SCHEMA,
                "status": "complete",
                "manifest_sha256": driver.sha256_file(manifest_path),
                "cells_total": len(manifest["schedule"]),
                "cells_completed": len(manifest["schedule"]),
                "elapsed_seconds": 10,
                "records": records,
            },
        )
        return root, manifest, records

    def test_all_three_comparisons_use_protocol_thresholds_and_report_regressions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = self._fixture(directory)
            result = summarize.summarize(root)

        self.assertEqual(result["formal_status"], "complete")
        comparisons = {
            (row["arm"], row["control"]): row for row in result["groups"][0]["comparisons"]
        }
        self.assertEqual(comparisons[("cache", "scan")]["classification"], "bounded-benefit")
        self.assertNotIn("regression_measures", comparisons[("cache", "scan")])
        self.assertEqual(comparisons[("candidates", "scan")]["classification"], "regression")
        self.assertEqual(
            comparisons[("candidates", "scan")]["regression_measures"], ["execution"]
        )
        self.assertEqual(comparisons[("candidates", "cache")]["classification"], "regression")
        self.assertEqual(
            comparisons[("candidates", "cache")]["regression_measures"], ["execution"]
        )

    def test_missing_and_failed_cells_force_incomplete_and_preserve_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest, _ = self._fixture(directory)
            missing_cell, failed_cell = manifest["schedule"][:2]
            (root / "measurement" / f"cell-{missing_cell['ordinal']:03d}" / "record.json").unlink()
            failed_path = root / "measurement" / f"cell-{failed_cell['ordinal']:03d}" / "record.json"
            failed = {
                "cell": failed_cell,
                "status": "failed",
                "failure": {"type": "CellFailure", "message": "synthetic failure"},
                "available_files": ["gnu-time.txt"],
            }
            _write_json(failed_path, failed)
            result = summarize.summarize(root)

        self.assertEqual(result["recorded_state_status"], "complete")
        self.assertEqual(result["formal_status"], "incomplete")
        self.assertEqual(result["complete_cells"], 97)
        details = {entry["cell"]["ordinal"]: entry for entry in result["incomplete_cells"]}
        self.assertEqual(details[missing_cell["ordinal"]]["evidence_status"], "missing_record")
        self.assertEqual(details[failed_cell["ordinal"]]["failure"], failed["failure"])
        self.assertEqual(details[failed_cell["ordinal"]]["available_files"], ["gnu-time.txt"])

    def test_rejects_manifest_report_and_cell_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = self._fixture(directory)
            state_path = root / "state.json"
            state = json.loads(state_path.read_text())
            state["manifest_sha256"] = "0" * 64
            _write_json(state_path, state)
            with self.assertRaisesRegex(ValueError, "state manifest hash mismatch"):
                summarize.summarize(root)

        with tempfile.TemporaryDirectory() as directory:
            root, manifest, _ = self._fixture(directory)
            cell = manifest["schedule"][0]
            report_path = root / "measurement" / f"cell-{cell['ordinal']:03d}" / "stage-c-report.json"
            report = json.loads(report_path.read_text())
            report["records"][0]["phases"]["plan_read_ns"] = 2
            _write_json(report_path, report)
            with self.assertRaisesRegex(ValueError, "stage-c report hash mismatch"):
                summarize.summarize(root)

        with tempfile.TemporaryDirectory() as directory:
            root, manifest, _ = self._fixture(directory)
            cell = manifest["schedule"][0]
            record_path = root / "measurement" / f"cell-{cell['ordinal']:03d}" / "record.json"
            record = json.loads(record_path.read_text())
            record["cell"] = copy.deepcopy(record["cell"])
            record["cell"]["arm"] = "cache"
            _write_json(record_path, record)
            with self.assertRaisesRegex(ValueError, "record identity mismatch"):
                summarize.summarize(root)

    def test_rejects_nonpositive_phase_and_rss_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest, _ = self._fixture(directory)
            cell = manifest["schedule"][0]
            cell_dir = root / "measurement" / f"cell-{cell['ordinal']:03d}"
            report_path = cell_dir / "stage-c-report.json"
            report = json.loads(report_path.read_text())
            report["records"][0]["phases"]["batch_execution_ns"] = 0
            _write_json(report_path, report)
            record_path = cell_dir / "record.json"
            record = json.loads(record_path.read_text())
            record["stage_c_report_sha256"] = driver.sha256_file(report_path)
            _write_json(record_path, record)
            with self.assertRaisesRegex(ValueError, "phase batch_execution_ns"):
                summarize.summarize(root)

        with tempfile.TemporaryDirectory() as directory:
            root, manifest, _ = self._fixture(directory)
            cell = manifest["schedule"][0]
            cell_dir = root / "measurement" / f"cell-{cell['ordinal']:03d}"
            time_path = cell_dir / "gnu-time.txt"
            time_path.write_text("Maximum resident set size (kbytes): 0\n", encoding="utf-8")
            record_path = cell_dir / "record.json"
            record = json.loads(record_path.read_text())
            record["gnu_time"] = driver.parse_gnu_time(time_path.read_text())
            record["gnu_time_sha256"] = driver.sha256_file(time_path)
            _write_json(record_path, record)
            with self.assertRaisesRegex(ValueError, "RSS must be a finite positive number"):
                summarize.summarize(root)


if __name__ == "__main__":
    unittest.main()
