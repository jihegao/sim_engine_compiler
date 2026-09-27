from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "cases/simlox-air-support/preparation-resource-v1"
sys.path.insert(0, str(BUNDLE))
SPEC = importlib.util.spec_from_file_location("simlox_preparation_validate", BUNDLE / "validate.py")
assert SPEC and SPEC.loader
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


def contract(case_id: str) -> dict:
    return json.loads((BUNDLE / "contracts" / f"{case_id}.json").read_text())


def event_log(*rows: tuple[float, str]) -> list[dict]:
    text = "\n".join(f"Time: {hours} {body}" for hours, body in rows)
    return VALIDATE.parse_events(text)


class PreparationResourceBehaviorTests(unittest.TestCase):
    def test_b01_requires_real_preparation_and_launch_timestamps(self):
        events = event_log(
            (7.5, "<AIR-TYPE,0> preparation started, mission: <MISSION-BASIC,PREP-UNIT,0,0,0>"),
            (8.0, "<AIR-TYPE,0> preparation ended, mission: <MISSION-BASIC,PREP-UNIT,0,0,0>"),
            (8.0, "<MISSION-BASIC,PREP-UNIT,0,0,0> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (9.0, "<MISSION-BASIC,PREP-UNIT,0,0,0> mission completed: <AIR-TYPE,0>"),
        )
        result = VALIDATE.evaluate_behavior(events, contract("B01"), "fixed-30m")
        self.assertTrue(result["passed"], result["differences"])

    def test_b01_rejects_launch_only_evidence(self):
        events = event_log(
            (8.0, "<MISSION-BASIC,PREP-UNIT,0,0,0> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (9.0, "<MISSION-BASIC,PREP-UNIT,0,0,0> mission completed: <AIR-TYPE,0>"),
        )
        result = VALIDATE.evaluate_behavior(events, contract("B01"), "fixed-30m")
        self.assertFalse(result["passed"])
        assertions = {item["assertion"] for item in result["differences"]}
        self.assertIn("fixed_preparation_start", assertions)
        self.assertIn("fixed_preparation_end", assertions)

    def test_b01_rejects_wrong_aircraft_mission_and_missing_completion(self):
        events = event_log(
            (7.5, "system preparation task 0 on <WRONG-AIR,0> started"),
            (8.0, "system preparation task 0 on <WRONG-AIR,0> completed"),
            (8.0, "<WRONG-MISSION,PREP-UNIT,0,0,0> mission starting, duration: 1 : <WRONG-AIR,0>"),
        )
        result = VALIDATE.evaluate_behavior(events, contract("B01"), "fixed-30m")
        self.assertFalse(result["passed"])
        assertions = {item["assertion"] for item in result["differences"]}
        self.assertIn("fixed_mission_launch_identity", assertions)
        self.assertIn("fixed_mission_completion_identity_and_time", assertions)

    def test_b02_requires_each_serial_step_identity_and_boundary(self):
        events = event_log(
            (7.0, "<AIR-TYPE,0> preparation started, mission: <MISSION-BASIC,U,0>"),
            (7.0, "subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> started"),
            (7 + 1 / 6, "subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (7 + 1 / 6, "subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> started"),
            (7.5, "subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (7.5, "<AIR-TYPE,0> preparation ended, mission: <MISSION-BASIC,U,0>"),
            (8.0, "<MISSION-BASIC,U,0> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (9.0, "<MISSION-BASIC,U,0> mission completed: <AIR-TYPE,0>"),
        )
        result = VALIDATE.evaluate_behavior(
            events, contract("B02"), "serial-10m-20m"
        )
        self.assertTrue(result["passed"], result["differences"])

    def test_b02_rejects_scalar_duration_timeline_and_wrong_sequence(self):
        events = event_log(
            (7.0, "<AIR-TYPE,0> preparation started, mission: <MISSION-BASIC,U,0>"),
            (7.0, "subtask 0 seqno 2 within system preparation task 0 on <AIR-TYPE,0> started"),
            (7.25, "subtask 0 seqno 2 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (7.25, "subtask 1 seqno 1 within system preparation task 0 on <AIR-TYPE,0> started"),
            (7.75, "subtask 1 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (7.75, "<AIR-TYPE,0> preparation ended, mission: <MISSION-BASIC,U,0>"),
            (8.0, "<MISSION-BASIC,U,0> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (9.0, "<MISSION-BASIC,U,0> mission completed: <AIR-TYPE,0>"),
        )
        result = VALIDATE.evaluate_behavior(events, contract("B02"), "serial-10m-20m")
        self.assertFalse(result["passed"])
        self.assertIn(
            "serial_preparation_timeline",
            {item["assertion"] for item in result["differences"]},
        )

    def test_b03_accepts_native_sequence_numbers_with_input_bound_recipes(self):
        events = event_log(
            (7.5, "<AIR-TYPE,0> preparation started, mission: <COLD-FIRST,U,0>"),
            (7.5, "subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> started"),
            (7 + 2 / 3, "subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (7 + 2 / 3, "subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> started"),
            (8.0, "subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> completed"),
            (8.0, "<AIR-TYPE,0> preparation ended, mission: <COLD-FIRST,U,0>"),
            (8.0, "<COLD-FIRST,U,0> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (9.0, "<COLD-FIRST,U,0> mission completed: <AIR-TYPE,0>"),
            (11 + 5 / 6, "<AIR-TYPE,0> preparation started, mission: <HOT-SORTIE,U,1>"),
            (11 + 5 / 6, "subtask 2 seqno 1 within system preparation task 1 on <AIR-TYPE,0> started"),
            (12.0, "subtask 2 seqno 1 within system preparation task 1 on <AIR-TYPE,0> completed"),
            (12.0, "<AIR-TYPE,0> preparation ended, mission: <HOT-SORTIE,U,1>"),
            (12.0, "<HOT-SORTIE,U,1> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (13.0, "<HOT-SORTIE,U,1> mission completed: <AIR-TYPE,0>"),
            (15 + 5 / 6, "<AIR-TYPE,0> preparation started, mission: <HOT-SORTIE,U,2>"),
            (15 + 5 / 6, "subtask 3 seqno 1 within system preparation task 2 on <AIR-TYPE,0> started"),
            (16.0, "subtask 3 seqno 1 within system preparation task 2 on <AIR-TYPE,0> completed"),
            (16.0, "<AIR-TYPE,0> preparation ended, mission: <HOT-SORTIE,U,2>"),
            (16.0, "<HOT-SORTIE,U,2> mission starting, duration: 1 : <AIR-TYPE,0>"),
            (17.0, "<HOT-SORTIE,U,2> mission completed: <AIR-TYPE,0>"),
        )
        result = VALIDATE.evaluate_behavior(events, contract("B03"), "explicit-cold-hot")
        self.assertTrue(result["passed"], result["differences"])

        events[8]["body"] = events[8]["body"].replace("HOT-SORTIE", "COLD-FIRST")
        result = VALIDATE.evaluate_behavior(events, contract("B03"), "explicit-cold-hot")
        self.assertFalse(result["passed"])
        self.assertIn(
            "explicit_recipe_mission_timeline",
            {item["assertion"] for item in result["differences"]},
        )

    def test_resource_cases_reject_the_preparation_only_parser(self):
        for case_id, variant_id in (
            ("C01", "capacity-1"),
            ("C02", "both-available"),
            ("C03", "staffing-1"),
        ):
            with self.subTest(case_id=case_id), self.assertRaisesRegex(
                ValueError, "requires validate_resources"
            ):
                VALIDATE.evaluate_behavior([], contract(case_id), variant_id)


class PreparationResourceEvidenceGateTests(unittest.TestCase):
    @staticmethod
    def recipe_report(case_id: str) -> dict:
        interval_count = 24 if case_id == "B02" else 40
        preparation = {14: 1.0} if case_id == "B02" else {15: 1.0, 23: 1 / 3, 31: 1 / 3}
        prepared_wait = {15} if case_id == "B02" else set()
        flights = {16, 17} if case_id == "B02" else {16, 17, 24, 25, 32, 33}
        successes = {15} if case_id == "B02" else {16, 24, 32}
        columns = [
            "UNID", "SID", "STINT", "ETINT", "FTMO", "NPSTA", "NPSUC",
            "NSYMA", "NSYMP", "NSYMO", "NSYRY",
        ]
        rows = []
        for index in range(interval_count):
            prep = preparation.get(index, 0.0)
            flight = 1.0 if index in flights else 0.0
            active = prep + flight + (1.0 if index in prepared_wait else 0.0)
            rows.append([
                "Total over all Units", "Total over all Systems", index / 2,
                (index + 1) / 2, flight, int(index in preparation),
                int(index in successes), active, prep, flight, 1 - active,
            ])
        return {
            "report": {
                "tables": [
                    {"name": "ProblemDescription", "columns": [{"name": "PDESC"}], "instances": [{"rows": [[case_id]]}]},
                    {"name": "ResultSummary", "columns": [{"name": name} for name in ("NREP", "MSTF", "MSUF")], "instances": [{"rows": [[1, 1, 1]]}]},
                    {"name": "SystemResults", "columns": [{"name": name} for name in columns], "instances": [{"rows": rows}]},
                    {"name": "StockTotalResults", "columns": [{"name": "STINT"}], "instances": [{"rows": []}]},
                ]
            }
        }

    def test_unknown_native_warning_is_rejected(self):
        log = (
            "(warning #999) unexpected conversion fallback\n"
            "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0\n"
        )
        with self.assertRaisesRegex(ValueError, r"unknown_warnings=\['999'\]"):
            VALIDATE.conversion_result(log, ["108", "126"])

    def test_whitelisted_native_warnings_are_counted(self):
        log = (
            "(warning #108) ENLOG enabled\n"
            "(warning #126) item-free system\n"
            "Input conversion completed. Errors: 0, Warnings: 2, Notes: 1\n"
        )
        result = VALIDATE.conversion_result(log, ["108", "126"])
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["warnings"], 2)

    def test_warning_allowlist_conditions_are_checked_against_input(self):
        def table(name, columns, rows):
            return {
                "name": name,
                "columns": [{"name": column} for column in columns],
                "instances": [{"rows": rows}],
            }

        document = {
            "model": {
                "tables": [
                    table("Control", ["ENLOG"], [["Y"]]),
                    table("Item", ["IID"], []),
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(document))
            self.assertEqual(
                VALIDATE.allowed_warnings_for_input(contract("B01"), path),
                ["108", "126"],
            )
            document["model"]["tables"][0]["instances"][0]["rows"] = [["N"]]
            path.write_text(json.dumps(document))
            self.assertEqual(
                VALIDATE.allowed_warnings_for_input(contract("B01"), path), ["126"]
            )

    def test_report_normalization_does_not_change_raw_bytes(self):
        raw = b'{"report":{"tables":[],},}'
        normalized = VALIDATE._remove_trailing_commas(raw)
        self.assertEqual(json.loads(normalized), {"report": {"tables": []}})
        self.assertEqual(raw, b'{"report":{"tables":[],},}')

    def test_roundtrip_check_is_recomputed_from_raw_artifacts(self):
        model = {
            "model": {
                "tables": [
                    {
                        "name": "Resource",
                        "columns": [{"name": "RID"}, {"name": "RQTY"}],
                        "instances": [{"rows": [["P-CREW", 1]]}],
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "input.json").write_text(json.dumps(model))
            (run / "roundtrip-raw.json").write_text(json.dumps(model))
            import binding

            recorded = {
                "all_equal": True,
                "changed": {},
                "input_sha256": binding.sha256(run / "input.json"),
                "roundtrip_sha256": binding.sha256(run / "roundtrip-raw.json"),
                "nonempty_business_tables": 1,
            }
            (run / "roundtrip-check.json").write_text(json.dumps(recorded))
            self.assertTrue(VALIDATE.roundtrip_result(run)["all_equal"])
            exported = json.loads(json.dumps(model))
            exported["model"]["tables"][0]["instances"][0]["rows"][0][1] = 2
            (run / "roundtrip-raw.json").write_text(json.dumps(exported))
            with self.assertRaisesRegex(ValueError, "disagrees with raw artifacts"):
                VALIDATE.roundtrip_result(run)

    def test_b01_report_requires_mission_system_and_preparation_results(self):
        system_rows = []
        for index in range(24):
            start = index * 0.5
            end = start + 0.5
            in_allocated = start >= 7.5 and end <= 9
            in_reserved = start >= 7.5 and end <= 8
            in_flight = start >= 8 and end <= 9
            system_rows.append(
                [
                    "Total over all Units",
                    "Total over all Systems",
                    start,
                    end,
                    int(in_flight),
                    int(start == 7.5),
                    int(in_allocated),
                    int(in_reserved),
                    int(in_flight),
                    int(not in_allocated),
                ]
            )
        report = {
            "report": {
                "tables": [
                    {
                        "name": "ResultSummary",
                        "columns": [
                            {"name": "NREP"},
                            {"name": "MSTF"},
                            {"name": "MSUF"},
                        ],
                        "instances": [{"rows": [[1, 1, 1]]}],
                    },
                    {
                        "name": "SystemResults",
                        "columns": [
                            {"name": "UNID"},
                            {"name": "SID"},
                            {"name": "STINT"},
                            {"name": "ETINT"},
                            {"name": "FTMO"},
                            {"name": "NPSTA"},
                            {"name": "NSYMA"},
                            {"name": "NSYMP"},
                            {"name": "NSYMO"},
                            {"name": "NSYRY"},
                        ],
                        "instances": [{"rows": system_rows}],
                    },
                    {
                        "name": "ProblemDescription",
                        "columns": [{"name": "PDESC"}],
                        "instances": [{"rows": [["B01"]]}],
                    },
                    {
                        "name": "StockTotalResults",
                        "columns": [{"name": "STINT"}],
                        "instances": [{"rows": []}],
                    },
                ]
            }
        }
        result = VALIDATE.evaluate_report(report, contract("B01"), "fixed-30m")
        self.assertTrue(result["passed"], result["differences"])
        # Preserve the aggregate NPSTA total while moving it to the wrong
        # interval; the per-interval gate must reject this timeline.
        rows = report["report"]["tables"][1]["instances"][0]["rows"]
        rows[15][5] = 0
        rows[0][5] = 1
        result = VALIDATE.evaluate_report(report, contract("B01"), "fixed-30m")
        self.assertFalse(result["passed"])
        self.assertIn(
            "preparation_start_interval_profile",
            {item["assertion"] for item in result["differences"]},
        )
        rows[0][5] = 0
        rows[15][5] = 1.9
        result = VALIDATE.evaluate_report(report, contract("B01"), "fixed-30m")
        self.assertFalse(result["passed"])
        self.assertIn(
            "preparation_start_interval_profile",
            {item["assertion"] for item in result["differences"]},
        )

    def test_b03_report_rejects_shifted_hot_preparation_profile(self):
        report = self.recipe_report("B03")
        result = VALIDATE.evaluate_report(report, contract("B03"), "explicit-cold-hot")
        self.assertTrue(result["passed"], result["differences"])
        rows = report["report"]["tables"][2]["instances"][0]["rows"]
        rows[23][8] = 0
        rows[22][8] = 1 / 3
        result = VALIDATE.evaluate_report(report, contract("B03"), "explicit-cold-hot")
        self.assertFalse(result["passed"])
        self.assertIn(
            "recipe_interval_profile",
            {item["assertion"] for item in result["differences"]},
        )

    def test_b03_input_mapping_rejects_unbound_recipe_duration(self):
        source = BUNDLE / "native" / "B03--explicit-cold-hot.json"
        document = json.loads(source.read_text())
        self.assertIn("MissionPreparation", VALIDATE.validate_input_mapping(contract("B03"), source))
        table = next(
            table for table in document["model"]["tables"]
            if table["name"] == "MissionPreparation"
        )
        duration = next(
            index for index, column in enumerate(table["columns"])
            if column["name"] == "DURN"
        )
        table["instances"][0]["rows"][0][duration] = 0.75
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.json"
            changed.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "contract row"):
                VALIDATE.validate_input_mapping(contract("B03"), changed)


if __name__ == "__main__":
    unittest.main()
