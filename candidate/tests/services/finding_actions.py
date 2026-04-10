from typing import Any, Optional

from clients.dashboard_client import DashboardClient
from data_builders.finding_payloads import FindingPayloadBuilder


class FindingActions:
    """Execute common finding operations via the Dashboard API.

    Each action starts with a default payload from ``FindingPayloadBuilder``.
    Extra keyword arguments override default payload fields or add new ones.
    """

    def __init__(self, api_cl: DashboardClient):
        self._dashboard_api = api_cl

    def create(
        self,
        asset_id: int,
        vulnerability_id: int,
        scanner: str = "pytest",
        notes: Optional[str] = None,
        **overrides: Any,
    ) -> dict:
        """Create a finding and return the response dict."""
        payload = FindingPayloadBuilder.create(asset_id, vulnerability_id, scanner, notes)
        payload = payload | overrides if overrides else payload

        resp = self._dashboard_api.create_finding(payload)
        assert resp.status_code == 201, f"Failed to create finding: {resp.text}"
        return resp.json()

    def create_with_status(
        self,
        asset_id: int,
        vulnerability_id: int,
        status: str,
        scanner: str = "pytest",
        notes: Optional[str] = None,
        **overrides: Any,
    ) -> dict:
        """Create a finding and then update its status."""
        finding = self.create(asset_id, vulnerability_id, scanner, notes, **overrides)

        resp = self._dashboard_api.update_finding_status_by_id(
            finding["id"],
            status,
            notes=notes,
        )
        assert resp.status_code == 200, f"Failed to set status '{status}': {resp.text}"
        return resp.json()

    def update_status(
        self,
        finding_id: int,
        status: str,
        notes: Optional[str] = None,
    ) -> dict:
        """Update status of an existing finding and return the response dict."""
        resp = self._dashboard_api.update_finding_status_by_id(finding_id, status, notes=notes)
        assert resp.status_code == 200, f"Failed to set status '{status}': {resp.text}"
        return resp.json()

    def dismiss(self, finding_id: int) -> None:
        """Dismiss a finding. Accepts 204 (dismissed) or 404 (already gone)."""
        resp = self._dashboard_api.dismiss_finding_by_id(finding_id)
        assert resp.status_code in (204, 404), (
            f"Unexpected response dismissing finding {finding_id}: {resp.status_code}"
        )