"""Aircraft Business IR vocabulary and lowering adapter."""
from .task_asset import TaskAssetDomain

ADAPTER = TaskAssetDomain(
    domain="aircraft", asset_key="fleet", job_key="missions", outage_key="maintenance"
)
