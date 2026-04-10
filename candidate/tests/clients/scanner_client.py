"""HTTP client for the Scanner Service (port 8001)."""
from config.settings import SCANNER_URL
from clients.http_base_client import HttpBaseClient


class ScannerClient(HttpBaseClient):
    def __init__(self, base_url: str = SCANNER_URL):
        super().__init__(base_url)

    # --- Assets ---

    def list_assets(self, **params):
        return self.get("/assets", **params)

    def get_asset_by_id(self, asset_id: int):
        return self.get(f"/assets/{asset_id}")

    def create_asset(self, payload: dict):
        return self.post("/assets", payload)

    def update_asset_by_id(self, asset_id: int, **fields):
        return self.put(f"/assets/{asset_id}", fields)

    def deactivate_asset_by_id(self, asset_id: int):
        return self.delete(f"/assets/{asset_id}")

    # --- Scans ---

    def list_scans(self, **params):
        return self.get("/scans", **params)

    def get_scan_by_id(self, scan_id: int):
        return self.get(f"/scans/{scan_id}")

    def create_scan(self, asset_id: int, scanner_name: str, vulnerability_ids: list[int]):
        return self.post("/scans", {
            "asset_id": asset_id,
            "scanner_name": scanner_name,
            "vulnerability_ids": vulnerability_ids,
        })