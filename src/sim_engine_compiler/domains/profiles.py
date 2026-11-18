"""Registered domain profiles.

Selection happens once from the canonical schema or the persisted Business
version. Aircraft-support-v1 stays on its existing importer and pack. Other
registered schemas never enter that importer and therefore never receive its
default aircraft entities.
"""

from __future__ import annotations

from typing import Any

from sim_engine_compiler.domains.aircraft_support.pack import PACK as AIRCRAFT_PACK
from sim_engine_compiler.domains.multi_server_queue.pack import PACK as QUEUE_PACK
from sim_engine_compiler.ir.layers import reject

PACKS = (AIRCRAFT_PACK, QUEUE_PACK)
BY_SCHEMA = {pack.input_schema: pack for pack in PACKS}
BY_DOMAIN = {(pack.name, pack.version): pack for pack in PACKS}


def pack_for_schema(schema: Any):
    pack = BY_SCHEMA.get(schema)
    if pack is None:
        reject(
            "schema_version",
            f"canonical schema {schema!r} is not a registered domain profile",
            code="unsupported_profile",
        )
    return pack


def pack_for_payload(payload: Any):
    source = payload.get("source") if isinstance(payload, dict) else None
    schema = source.get("schema_version") if isinstance(source, dict) else None
    if schema is None:
        return AIRCRAFT_PACK
    return pack_for_schema(schema)


def pack_for_domain(name: Any, version: Any):
    pack = BY_DOMAIN.get((name, version))
    if pack is None:
        reject(
            "manifest.domain_pack",
            f"domain pack {name!r} {version!r} is not registered",
            code="unsupported_domain_pack",
        )
    return pack


def import_registered_canonical(inputs: Any):
    """Load a canonical document through the profile registered for its schema."""
    schema = inputs.get("schema_version") if isinstance(inputs, dict) else None
    return pack_for_schema(schema).import_canonical(inputs)


def registered_profiles() -> tuple[str, ...]:
    return tuple(pack.domain_profile for pack in PACKS)
