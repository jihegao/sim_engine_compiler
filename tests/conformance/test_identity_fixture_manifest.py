"""Fixed, independently reloadable inputs for the public identity boundary."""

import hashlib
import json
from pathlib import Path

import pytest

from sim_engine_compiler.compiler.layout import compile_core, lineage
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/identity_contract"


@pytest.mark.parametrize("case", ["b1", "f35"])
def test_frozen_files_and_independent_layer_reload(case):
    entry = json.loads((FIXTURES / "manifest.json").read_text())["cases"][case]
    assert hashlib.sha256((ROOT / entry["canonical_source"]).read_bytes()).hexdigest() == entry["canonical_file_sha256"]
    for name, expected in entry["files"].items():
        assert hashlib.sha256((FIXTURES / case / name).read_bytes()).hexdigest() == expected
    values = {name: json.loads((FIXTURES / case / f"{name}.json").read_text())
              for name in ("business", "core", "plan", "lineage")}
    business = BusinessIR.from_dict(values["business"])
    core = CoreIR.from_dict(values["core"])
    assert lower_business(business).to_dict() == values["core"]
    plan = compile_core(core)
    assert json.loads(json.dumps(plan.to_dict())) == values["plan"]
    assert lineage(business, core, plan) == values["lineage"]
