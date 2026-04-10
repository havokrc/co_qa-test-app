"""HTTP client for the Dashboard API"""
from clients.http_base_client import HttpBaseClient
from config.settings import DASHBOARD_URL


class DashboardClient(HttpBaseClient):
    def __init__(self, base_url: str = DASHBOARD_URL):
        super().__init__(base_url)

    # --- Findings ---

    def list_findings(self, **params):
        return self.get("/findings", **params)

    def get_finding_by_id(self, finding_id: int):
        return self.get(f"/findings/{finding_id}")

    def create_finding(self, payload: dict):
        return self.post("/findings", payload)

    def update_finding_status_by_id(self, finding_id: int, status: str, notes: str = None):
        payload = {"status": status}
        if notes:
            payload["notes"] = notes
        return self.put(f"/findings/{finding_id}/status", payload)

    def dismiss_finding_by_id(self, finding_id: int):
        return self.delete(f"/findings/{finding_id}")

    def search_findings(self, q: str):
        return self.get("/findings/search", q=q)

    # --- Stats ---

    def risk_score(self):
        return self.get("/stats/risk-score")

    def summary(self):
        return self.get("/stats/summary")

    # --- Vulnerabilities ---

    def list_vulnerabilities(self, **params):
        return self.get("/vulnerabilities", **params)

    def get_vulnerability_by_id(self, vuln_id: int):
        return self.get(f"/vulnerabilities/{vuln_id}")