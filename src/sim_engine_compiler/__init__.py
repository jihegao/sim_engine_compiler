"""Business simulation compiler and independent Python/Rust runtimes."""

__version__ = "0.1.0"

from .native import native_available, run_batch, run_canonical_batch, run_plan
from .compiler import compile_model
from .reference import AbmTickRuntime, run_abm_batch, run_abm_plan
from .product import (
    ProductError, batch_bundle, compile_bundle, diff_runs, inspect_model,
    load_bundle, run_bundle, seal_business, validate_business,
)

__all__ = [
    "native_available", "run_batch", "run_canonical_batch", "run_plan",
    "compile_model", "AbmTickRuntime", "run_abm_batch", "run_abm_plan",
    "ProductError", "batch_bundle", "compile_bundle", "diff_runs", "inspect_model",
    "load_bundle", "run_bundle", "seal_business", "validate_business",
]
