"""Restricted two-server queue profile.

This package owns the queue schema, lowering, and reference runtime. The
generic aircraft compiler and aircraft runtime do not branch on this profile.
"""

from .model import EXAMPLE_INPUT, PROFILE, SCHEMA, import_canonical
from .pack import PACK

__all__ = ["EXAMPLE_INPUT", "PACK", "PROFILE", "SCHEMA", "import_canonical"]
