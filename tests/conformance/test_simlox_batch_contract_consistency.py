from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "cases" / "simlox-air-support"
BATCH = CASES / "preparation-resource-v1"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "simlox_preparation_resource_generate_consistency_test",
        BATCH / "generate.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_generator()


def contract(case_id: str) -> dict:
    return read_json(BATCH / "contracts" / f"{case_id}.json")


def active_candidate(case_id: str, variant_id: str | None = None) -> dict:
    manifest = read_json(BATCH / "native" / "manifest.json")
    matches = [
        candidate
        for candidate in manifest["candidates"]
        if candidate["case_id"] == case_id
        and (variant_id is None or candidate["variant_id"] == variant_id)
    ]
    assert len(matches) == 1
    return matches[0]


def parameters(case_id: str) -> dict:
    manifest = read_json(BATCH / "native" / "manifest.json")
    paths = {
        candidate["parameter_path"]
        for candidate in manifest["candidates"]
        if candidate["case_id"] == case_id
    }
    assert len(paths) == 1
    return read_json(BATCH / paths.pop())


def native(case_id: str, variant_id: str) -> dict:
    return read_json(BATCH / active_candidate(case_id, variant_id)["path"])


def rows(model: dict, table_name: str) -> list[dict]:
    table = next(
        table for table in model["model"]["tables"] if table["name"] == table_name
    )
    columns = [column["name"] for column in table["columns"]]
    return [
        dict(zip(columns, row, strict=True))
        for instance in table["instances"]
        for row in instance["rows"]
    ]


def test_contract_parameter_and_manifest_variant_sets_are_identical():
    manifest = read_json(BATCH / "native" / "manifest.json")
    manifest_pairs = [
        (candidate["case_id"], candidate["variant_id"])
        for candidate in manifest["candidates"]
    ]
    manifest_revisions = [
        (
            candidate["case_id"],
            candidate["variant_id"],
            candidate["candidate_revision"],
        )
        for candidate in manifest["candidates"]
    ]
    expected_pairs: list[tuple[str, str]] = []

    for case_id in GENERATOR.CASES:
        case_contract = contract(case_id)
        case_parameters = parameters(case_id)
        contract_variants = {
            variant["variant_id"] for variant in case_contract["variants"]
        }
        parameter_variants = {
            variant["variant_id"] for variant in case_parameters["variants"]
        }
        deferred = case_contract.get("deferred_variants", [])
        deferred_ids = {variant["variant_id"] for variant in deferred}

        assert contract_variants == parameter_variants
        assert contract_variants.isdisjoint(deferred_ids)
        assert all(
            variant["status"] == "deferred_not_generated_in_v1"
            for variant in deferred
        )
        assert case_contract["parent_case"] == case_parameters["parent_case"]
        assert case_contract["status"] == "planned_native_unverified"
        assert case_parameters["status"] == "planned_native_acceptance"
        expected_pairs.extend((case_id, variant_id) for variant_id in parameter_variants)

    assert manifest["status"] == "planned_native_acceptance"
    assert manifest["candidate_count"] == len(manifest_pairs) == 12
    assert len(manifest_pairs) == len(set(manifest_pairs))
    assert len(manifest_revisions) == len(set(manifest_revisions))
    assert set(manifest_pairs) == set(expected_pairs)
    assert not any(
        (case_id, deferred["variant_id"]) in manifest_pairs
        for case_id in GENERATOR.CASES
        for deferred in contract(case_id).get("deferred_variants", [])
    )


def test_manifest_hashes_bind_each_parameter_and_generated_native_candidate():
    manifest = read_json(BATCH / "native" / "manifest.json")

    for candidate in manifest["candidates"]:
        parameter_path = BATCH / candidate["parameter_path"]
        native_path = BATCH / candidate["path"]
        parent_diff_path = BATCH / candidate["parent_diff_path"]
        parent_diff = read_json(parent_diff_path)
        assert candidate["parameter_sha256"] == sha256(parameter_path)
        assert candidate["input_sha256"] == sha256(native_path)
        assert parent_diff_path.is_file()
        assert parent_diff["case_id"] == candidate["case_id"]
        assert parent_diff["variant_id"] == candidate["variant_id"]
        assert parent_diff["status"] == "planned_native_acceptance"
        assert candidate["native_verified"] is False


def test_resource_allocation_point_matches_control_allocation_point():
    for case_id, variant_id in (
        ("C01", "capacity-2"),
        ("C02", "both-available"),
        ("C03", "staffing-2"),
    ):
        model = native(case_id, variant_id)
        allocation_point = rows(model, "Control")[0]["APID"]
        assert allocation_point == "AIR_BASIC"
        assert {record["POINT"] for record in rows(model, "ResourceAllocation")} == {
            allocation_point
        }


def test_generator_rejects_resource_allocation_point_not_selected_by_control():
    case_parameters = parameters("C03")
    model = GENERATOR.build(case_parameters, "staffing-2")
    resource_table = next(
        table
        for table in model["model"]["tables"]
        if table["name"] == "ResourceAllocation"
    )
    point_index = next(
        index
        for index, column in enumerate(resource_table["columns"])
        if column["name"] == "POINT"
    )
    resource_table["instances"][0]["rows"][0][point_index] = "AIR-TYPE"

    with pytest.raises(ValueError, match="ResourceAllocation: unresolved reference"):
        GENERATOR.validate_native(model, case_parameters)


def test_b02_active_revision_and_failed_snapshot_remain_separate():
    manifest = read_json(BATCH / "native" / "manifest.json")
    active = active_candidate("B02", "serial-10m-20m")
    failed = [
        candidate
        for candidate in manifest["failed_candidates"]
        if candidate["case_id"] == "B02"
        and candidate["variant_id"] == "serial-10m-20m"
    ]

    assert active["candidate_revision"] == "1.0.1"
    assert active["path"] == "native/B02--serial-10m-20m--v1.0.1.json"
    assert len(failed) == 1
    assert failed[0]["candidate_revision"] == "1.0.0"
    assert failed[0]["status"] == "native_rejected"
    assert failed[0]["diagnostic"] == "MissionPreparation error #200"
    assert failed[0]["path"] == "native/B02--serial-10m-20m.json"
    assert failed[0]["input_sha256"] == (
        "60c80a4af566de353e31cd8298143d024872b38e699472a4d015cadfa882cb24"
    )
    assert sha256(BATCH / failed[0]["path"]) == failed[0]["input_sha256"]
    assert active["path"] != failed[0]["path"]
    assert active["input_sha256"] != failed[0]["input_sha256"]
    failed_contract = contract("B02")["failed_candidate_revisions"]
    assert [item["candidate_revision"] for item in failed_contract] == ["1.0.0"]


def test_b02_breakdown_is_ordered_ten_plus_twenty_and_scalar_remains_45():
    case_contract = contract("B02")
    case_parameters = parameters("B02")
    model = native("B02", "serial-10m-20m")

    contract_preparation = case_contract["business_contract"]["preparation"]
    profile = case_parameters["preparation_profiles"][0]
    breakdown = rows(model, "TaskBreakDown")
    preparation = rows(model, "MissionPreparation")

    assert contract_preparation["scalar_duration"] == 45
    assert contract_preparation["effective_duration"] == 30
    assert [step["sequence"] for step in contract_preparation["steps"]] == [1, 2]
    assert [step["duration"] for step in contract_preparation["steps"]] == [10, 20]
    assert profile["aggregate_duration_minutes"] == 45
    assert case_parameters["candidate_revision"] == "1.0.1"
    assert case_parameters["mission_types"][0]["notice_lead_minutes"] == 60
    assert case_parameters["waves"][0]["planned_start_minutes"] == 480
    assert case_contract["business_contract"]["mission"]["notice"] == 420
    assert [step["duration_minutes"] for step in profile["steps"]] == [10, 20]
    assert [record["SEQ"] for record in breakdown] == [1, 2]
    assert [record["DURN"] for record in breakdown] == pytest.approx([10 / 60, 20 / 60])
    assert preparation[0]["DURN"] == pytest.approx(45 / 60)
    assert sum(record["DURN"] for record in breakdown) == pytest.approx(30 / 60)
    assert rows(model, "MissionType")[0]["NOPER"] == pytest.approx(60 / 60)


def test_b03_uses_explicit_cold_hot_ids_and_three_wave_recipes():
    case_contract = contract("B03")
    case_parameters = parameters("B03")
    model = native("B03", "explicit-cold-hot")

    sequence = case_contract["business_contract"]["mission_sequence"]
    profiles = {
        profile["mission_type_id"]: profile
        for profile in case_parameters["preparation_profiles"]
    }
    mission_types = {
        mission["id"]: mission for mission in case_parameters["mission_types"]
    }
    contract_recipes = case_contract["business_contract"]["recipes"]

    assert [mission["mission_type"] for mission in sequence] == [
        "COLD-FIRST",
        "HOT-SORTIE",
        "HOT-SORTIE",
    ]
    assert [mission["planned_launch"] for mission in sequence] == [480, 720, 960]
    assert [wave["mission_type_id"] for wave in case_parameters["waves"]] == [
        "COLD-FIRST",
        "HOT-SORTIE",
        "HOT-SORTIE",
    ]
    assert [wave["planned_start_minutes"] for wave in case_parameters["waves"]] == [
        480,
        720,
        960,
    ]
    assert [
        mission_types[mission_type]["notice_lead_minutes"]
        for mission_type in ("COLD-FIRST", "HOT-SORTIE")
    ] == [30, 10]
    expected_notices = [
        wave["planned_start_minutes"]
        - mission_types[wave["mission_type_id"]]["notice_lead_minutes"]
        for wave in case_parameters["waves"]
    ]
    assert expected_notices == [450, 710, 950]
    assert [mission["notice"] for mission in sequence] == expected_notices
    assert [profiles[mission["mission_type"]]["aggregate_duration_minutes"] for mission in sequence] == [30, 10, 10]
    assert case_contract["variants"][0]["expected_preparation_durations"] == [30, 10, 10]
    for mission_type, recipe in contract_recipes.items():
        profile = profiles[mission_type]
        assert recipe["task_id"] == profile["task_id"]
        assert [step["sequence"] for step in recipe["steps"]] == list(
            range(1, len(profile["steps"]) + 1)
        )
        assert [step["step_id"] for step in recipe["steps"]] == [
            step["id"] for step in profile["steps"]
        ]
        assert [step["duration"] for step in recipe["steps"]] == [
            step["duration_minutes"] for step in profile["steps"]
        ]

    native_mission_types = {
        record["MTID"]: record for record in rows(model, "MissionType")
    }
    assert set(native_mission_types) == {
        "COLD-FIRST",
        "HOT-SORTIE",
    }
    assert native_mission_types["COLD-FIRST"]["NOPER"] == pytest.approx(30 / 60)
    assert native_mission_types["HOT-SORTIE"]["NOPER"] == pytest.approx(10 / 60)
    assert [record["SPRID"] for record in rows(model, "OperationProfile")] == [
        "COLD-FIRST",
        "HOT-SORTIE",
        "HOT-SORTIE",
    ]
    assert [record["STIM"] for record in rows(model, "OperationProfile")] == [
        8,
        12,
        16,
    ]
    native_preparations = {
        record["MTID"]: record for record in rows(model, "MissionPreparation")
    }
    assert native_preparations["COLD-FIRST"]["DURN"] == pytest.approx(30 / 60)
    assert native_preparations["HOT-SORTIE"]["DURN"] == pytest.approx(10 / 60)


def test_c03_native_formation_and_notice_contract_is_exact():
    case_parameters = parameters("C03")
    model = native("C03", "staffing-2")
    mission = rows(model, "MissionType")

    assert case_parameters["aircraft_quantity"] == 2
    assert case_parameters["mission_types"][0]["aircraft_required"] == 2
    assert case_parameters["mission_types"][0]["minimum_aircraft"] == 2
    assert case_parameters["mission_types"][0]["notice_lead_minutes"] == 30
    assert len(mission) == 1
    assert mission[0]["NOS"] == 2
    assert mission[0]["MNOS"] == 2
    assert mission[0]["NOPER"] == pytest.approx(0.5)


def test_c03_staffing_variants_change_only_personnel_allocation_quantity():
    baseline = native("C03", "staffing-2")

    for variant_id, expected_quantity in (("staffing-1", 1), ("staffing-0", 0)):
        candidate = native("C03", variant_id)
        difference = GENERATOR.model_diff(baseline, candidate)
        assert difference["table_count"] == 1
        assert difference["added_row_count"] == 0
        assert difference["removed_row_count"] == 0
        assert difference["field_change_count"] == 1
        assert set(difference["tables"]) == {"ResourceAllocation"}
        changed = difference["tables"]["ResourceAllocation"]["changed"]
        assert len(changed) == 1
        assert changed[0]["key"]["RID"] == "P-CREW"
        assert changed[0]["fields"] == {
            "RQTY": {"parent": 2, "child": expected_quantity}
        }


def test_frozen_a01_a02_inputs_and_native_schema_retain_published_hashes():
    expected = {
        CASES / "A01-single-aircraft-single-mission" / "native-input.json": (
            "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
        ),
        CASES / "A02-single-aircraft-repeated-missions" / "native-input.json": (
            "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
        ),
        CASES / "native-schema.json": (
            "162679fd6e06e64c83f004417122379e773f47b1ea089c7e0c1a06f2f560c65e"
        ),
    }

    assert {path: sha256(path) for path in expected} == expected
    manifest = read_json(BATCH / "native" / "manifest.json")
    assert manifest["native_schema_sha256"] == expected[CASES / "native-schema.json"]
    assert GENERATOR.writer.SCHEMA_SHA256 == expected[CASES / "native-schema.json"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value.update({"unexpected_semantics": True}),
            "unknown or missing parameter field",
        ),
        (
            lambda value: value["units"].update({"authored_time": "hour"}),
            "invalid units",
        ),
        (
            lambda value: value["variants"][0]["resource_capacities"].update(
                {"UNKNOWN-RID": 1}
            ),
            "unresolved resource UNKNOWN-RID",
        ),
        (
            lambda value: value["mission_types"][0].update(
                {"notice_lead_minutes": 0.5}
            ),
            "expected integer",
        ),
    ],
)
def test_invalid_parameter_fields_are_rejected_instead_of_dropped(mutation, message):
    invalid = copy.deepcopy(parameters("C03"))
    mutation(invalid)

    with pytest.raises(ValueError, match=message):
        GENERATOR.validate_parameters(invalid)


def test_unknown_variant_is_rejected_instead_of_generating_a_default():
    with pytest.raises(ValueError, match="unknown variant missing-variant"):
        GENERATOR.build(parameters("B01"), "missing-variant")
