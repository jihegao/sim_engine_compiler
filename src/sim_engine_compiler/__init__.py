"""Business simulation compiler and independent Python/Rust runtimes."""

from .native import native_available, run_batch, run_plan

__version__ = "0.0.1"

__all__ = ["native_available", "run_batch", "run_plan"]
