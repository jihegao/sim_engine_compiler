"""Public canonical entry point; all production compilation traverses the IR layers."""
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.compiler.layout import compile_core


def compile_aircraft_support(inputs, *, semantic_profile="legacy-minute-v1"):
    return compile_core(lower_business(import_business_ir(inputs, semantic_profile=semantic_profile)))
