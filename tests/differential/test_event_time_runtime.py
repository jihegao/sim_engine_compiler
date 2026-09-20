from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
SYNTHETIC = ROOT / "tests" / "fixtures" / "synthetic"
F35_PLAN = (
    ROOT
    / "tests"
    / "fixtures"
    / "spare_mvp"
    / "f35-43day-5352a0d"
    / "execution-plan.json"
)


def _cargo() -> str:
    found = shutil.which("cargo")
    if found:
        return found
    rustup_default = Path.home() / ".cargo" / "bin" / "cargo"
    if rustup_default.exists():
        return str(rustup_default)
    raise AssertionError(
        "event-time Rust conformance requires cargo; install the pinned "
        "rust-toolchain.toml toolchain"
    )


class EventTimeRuntimeConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [
                _cargo(),
                "build",
                "--quiet",
                "--release",
                "--manifest-path",
                str(MANIFEST),
                "--bin",
                "sim-engine-runtime",
            ],
            cwd=ROOT,
            check=True,
        )
        executable = (
            "sim-engine-runtime.exe"
            if __import__("os").name == "nt"
            else "sim-engine-runtime"
        )
        cls.binary = ROOT / "rust" / "runtime" / "target" / "release" / executable
        cls.tempdir = tempfile.TemporaryDirectory(
            prefix="sim-engine-event-time-conformance-"
        )

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def _write_plan_variant(
        self,
        plan_path: Path,
        *,
        semantic_profile: str,
        phases: list[str] | None = None,
    ) -> Path:
        plan = json.loads(plan_path.read_text())
        plan["semantic_profile"] = semantic_profile
        if phases is not None:
            plan["phases"] = phases
        variant_index = len(list(Path(self.tempdir.name).iterdir()))
        destination = Path(self.tempdir.name) / (
            f"{plan_path.stem}-{semantic_profile}-{variant_index}.json"
        )
        destination.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        return destination

    def _write_raw_plan(self, name: str, plan: dict) -> Path:
        variant_index = len(list(Path(self.tempdir.name).iterdir()))
        destination = Path(self.tempdir.name) / f"{name}-{variant_index}.json"
        destination.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        return destination

    def _run(
        self,
        plan_path: Path,
        *,
        seed: int = 0,
        observation_level: str = "full",
        until: int | None = None,
    ) -> dict:
        output = Path(self.tempdir.name) / (
            f"{plan_path.stem}-seed-{seed}-{observation_level}-{until}-result.json"
        )
        command = [
            str(self.binary),
            str(plan_path),
            str(output),
            "--seed",
            str(seed),
            "--observation-level",
            observation_level,
        ]
        if until is not None:
            command.extend(("--until", str(until)))
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def assert_event_time_matches_legacy(self, plan_name: str) -> None:
        legacy_plan = SYNTHETIC / f"{plan_name}-execution-plan.json"
        event_plan = self._write_plan_variant(
            legacy_plan, semantic_profile="event-time-v2"
        )
        legacy = self._run(legacy_plan)
        event = self._run(event_plan)

        self.assertNotEqual(
            legacy["plan_fingerprint"],
            event["plan_fingerprint"],
            "changing the semantic profile must change the Plan fingerprint",
        )
        legacy_without_identity = copy.deepcopy(legacy)
        event_without_identity = copy.deepcopy(event)
        legacy_without_identity.pop("plan_fingerprint")
        event_without_identity.pop("plan_fingerprint")
        self.assertEqual(event_without_identity, legacy_without_identity)

    def assert_results_match_except_plan_identity(
        self, legacy: dict, event: dict
    ) -> None:
        self.assertNotEqual(legacy["plan_fingerprint"], event["plan_fingerprint"])
        legacy = copy.deepcopy(legacy)
        event = copy.deepcopy(event)
        legacy.pop("plan_fingerprint")
        event.pop("plan_fingerprint")
        self.assertEqual(event, legacy)

    def test_01_b1_daily_operations_matches_legacy(self):
        self.assert_event_time_matches_legacy("b1")

    def test_02_b3_upstream_transport_matches_legacy(self):
        self.assert_event_time_matches_legacy("b3-upstream-transport")

    def test_03_b2_failure_repair_matches_legacy(self):
        self.assert_event_time_matches_legacy("b2-failure-repair")

    def test_04_b2_preventive_maintenance_matches_legacy(self):
        self.assert_event_time_matches_legacy("b2-preventive-maintenance")

    def test_05_event_time_rejects_noncanonical_phase_order(self):
        legacy_plan = SYNTHETIC / "b1-execution-plan.json"
        raw = json.loads(legacy_plan.read_text())
        phases = list(raw["phases"])
        phases[0], phases[1] = phases[1], phases[0]
        invalid_plan = self._write_plan_variant(
            legacy_plan,
            semantic_profile="event-time-v2",
            phases=phases,
        )
        output = Path(self.tempdir.name) / "invalid-phase-result.json"
        completed = subprocess.run(
            [str(self.binary), str(invalid_plan), str(output), "--seed", "0"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "event-time-v2 requires the canonical legacy phase order",
            completed.stderr,
        )

    def test_06_f35_required_seeds_and_observation_levels_match_legacy(self):
        event_plan = self._write_plan_variant(
            F35_PLAN, semantic_profile="event-time-v2"
        )
        for observation_level in ("full", "summary"):
            for seed in (0, 1, 7):
                with self.subTest(observation_level=observation_level, seed=seed):
                    legacy = self._run(
                        F35_PLAN,
                        seed=seed,
                        observation_level=observation_level,
                    )
                    event = self._run(
                        event_plan,
                        seed=seed,
                        observation_level=observation_level,
                    )
                    self.assert_results_match_except_plan_identity(legacy, event)

    def test_07_f35_horizon_before_at_and_after_event_matches_legacy(self):
        event_plan = self._write_plan_variant(
            F35_PLAN, semantic_profile="event-time-v2"
        )
        for until in (299, 300, 301, 61919, 61920):
            with self.subTest(until=until):
                legacy = self._run(F35_PLAN, until=until)
                event = self._run(event_plan, until=until)
                self.assert_results_match_except_plan_identity(legacy, event)

    def test_08_postflight_created_after_dispatch_wakes_remote_spare_request(self):
        raw = json.loads((SYNTHETIC / "b1-execution-plan.json").read_text())
        # The cancellation creates postflight work in the phase after resource
        # dispatch. Its remote spare request must therefore wake the next minute.
        raw["missions"][1]["required_aircraft"] = 99
        raw["missions"][1]["min_required_aircraft"] = 99
        raw["activities"][2]["steps"][0]["spares"] = [["post-part", 1]]
        raw["resource_nodes"].append(
            {
                "index": 1,
                "node_id": "depot",
                "personnel_capacity": 0,
                "equipment_capacity": 0,
                "inventory": [["post-part", 1]],
                "organization_node_id": "depot",
                "source_path": "synthetic.depot",
            }
        )
        raw["supply_routes"] = [
            {
                "index": 0,
                "route_id": "depot-line",
                "source_node_index": 1,
                "destination_node_index": 0,
                "product_id": "post-part",
                "capacity": 1,
                "transport_minutes": 2,
                "supply_mode": "vertical",
                "relation_id": "",
                "source_path": "synthetic.route",
            }
        ]
        legacy_plan = self._write_raw_plan("postflight-remote-spare-legacy", raw)
        event_raw = copy.deepcopy(raw)
        event_raw["semantic_profile"] = "event-time-v2"
        event_plan = self._write_raw_plan(
            "postflight-remote-spare-event", event_raw
        )

        legacy = self._run(legacy_plan)
        event = self._run(event_plan)
        self.assert_results_match_except_plan_identity(legacy, event)

    def test_09_zero_duration_mission_returns_on_next_minute(self):
        raw = json.loads((SYNTHETIC / "b1-execution-plan.json").read_text())
        for mission in raw["missions"]:
            mission["duration_minutes"] = 0
        legacy_plan = self._write_raw_plan("zero-duration-mission-legacy", raw)
        event_raw = copy.deepcopy(raw)
        event_raw["semantic_profile"] = "event-time-v2"
        event_plan = self._write_raw_plan("zero-duration-mission-event", event_raw)

        legacy = self._run(legacy_plan)
        event = self._run(event_plan)
        self.assert_results_match_except_plan_identity(legacy, event)


if __name__ == "__main__":
    unittest.main()
