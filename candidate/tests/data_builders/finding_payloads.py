import time
from typing import Optional

_UNSET = object()

class FindingPayloadBuilder:
    """Build request payloads for finding-related endpoints."""

    @staticmethod
    def create(asset_id: int, vulnerability_id: int,
               scanner: Optional[str] = "pytest", notes: str =_UNSET) -> dict:
        """Payload for POST /findings."""
        if notes is _UNSET:
            notes = str(round(time.time() * 1000))
        return {
            "asset_id": asset_id,
            "vulnerability_id": vulnerability_id,
            "scanner": scanner,
            "notes": notes,
        }

    @staticmethod
    def update_status(status: str, notes: str = _UNSET) -> dict:
        """Payload for PUT /findings/{id}/status."""
        if notes is _UNSET:
            notes = str(round(time.time() * 1000))
        return {
            "status": status,
            "notes": notes,
        }