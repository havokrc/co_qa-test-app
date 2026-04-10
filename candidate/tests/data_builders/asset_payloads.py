from typing import Optional

_UNSET = object()


class AssetPayloadBuilder:
    """Build request payloads for asset-related endpoints."""

    @staticmethod
    def create(
        hostname: str,
        asset_type: str = "server",
        environment: str = "development",
        ip_address: Optional[str] = "10.99.0.1",
        os: Optional[str] = "Ubuntu 22.04",
    ) -> dict:
        """Payload for POST /assets."""
        payload = {
            "hostname": hostname,
            "asset_type": asset_type,
            "environment": environment,
            "ip_address": ip_address,
            "os": os,
        }
        return payload
