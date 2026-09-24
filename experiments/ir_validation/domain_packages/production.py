"""Production Business IR vocabulary and lowering adapter."""
from .task_asset import TaskAssetDomain

ADAPTER = TaskAssetDomain(
    domain="production", asset_key="machines", job_key="jobs", outage_key="outages"
)
