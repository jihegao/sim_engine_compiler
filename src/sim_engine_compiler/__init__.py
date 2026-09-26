"""Business simulation compiler and independent Python/Rust runtimes."""

from .native import native_available, run_batch, run_canonical_batch, run_plan
from .compiler import compile_model
from .reference import AbmTickRuntime, run_abm_batch, run_abm_plan

__version__ = "0.0.1"

__all__ = [
    "native_available", "run_batch", "run_canonical_batch", "run_plan",
    "compile_model", "AbmTickRuntime", "run_abm_batch", "run_abm_plan",
]
