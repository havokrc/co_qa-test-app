import pytest
import threading
from clients.dashboard_client import DashboardClient
from clients.scanner_client import ScannerClient


class TestScanCreatesFindings:
    def test_scan_creates_findings_visible_in_dashboard(
        self, scanner_cl: ScannerClient, api_cl: DashboardClient, created_asset
    ):
        """Title: Scan creates findings visible via Dashboard API.

        Steps:
        1. Create a scan for a valid asset with known vulnerability IDs.
        2. Assert scan response status is 201 and status is 'completed'.
        3. Assert findings_count equals number of vulnerabilities submitted.
        4. Query Dashboard API for findings filtered by asset_id.
        5. Assert created vulnerability IDs are present in findings list.
        """
        asset_id = created_asset["id"]
        vuln_ids = [1, 2]

        scan_resp = scanner_cl.create_scan(asset_id, "pytest-scanner", vuln_ids)
        assert scan_resp.status_code == 201
        scan = scan_resp.json()
        assert scan["status"] == "completed"
        assert scan["findings_count"] == len(vuln_ids)

        # Verify findings appear in Dashboard API filtered by asset
        findings_resp = api_cl.list_findings(asset_id=asset_id)
        assert findings_resp.status_code == 200
        created_ids = {f["vulnerability_id"] for f in findings_resp.json()["items"]}
        assert set(vuln_ids).issubset(created_ids)

    def test_scan_with_invalid_asset_returns_400(self, scanner_cl: ScannerClient):
        """Title: Scan request with invalid asset returns 400.

        Steps:
        1. Attempt to create a scan using a non-existent asset_id.
        2. Assert API returns HTTP 400.
        """
        resp = scanner_cl.create_scan(999999, "pytest-scanner", [1])
        assert resp.status_code == 400

    def test_scan_skips_invalid_vulnerability_ids(
        self, scanner_cl: ScannerClient, created_asset
    ):
        """Title: Scan skips invalid vulnerability IDs.

            Steps:
            1. Run a scan with a valid asset but non-existent vulnerability IDs.
            2. Assert API returns 201.
            3. Assert findings_count equals 0.
            """
        resp = scanner_cl.create_scan(created_asset["id"], "pytest-scanner", [999999])
        assert resp.status_code == 201
        assert resp.json()["findings_count"] == 0

    def test_scan_findings_count_matches_actual_findings_created(
        self, scanner_cl: ScannerClient, api_cl: DashboardClient, created_asset
    ):
        """Title: Scan findings_count matches actual findings in Dashboard.

        Steps:
        1. Run a scan with multiple valid vulnerability IDs.
        2. Capture findings_count from scan response.
        3. Query Dashboard API for findings filtered by asset_id.
        4. Assert reported count equals actual findings total.
        """
        asset_id = created_asset["id"]
        vuln_ids = [3, 4, 5]

        scan = scanner_cl.create_scan(asset_id, "pytest-scanner", vuln_ids).json()
        reported_count = scan["findings_count"]

        actual_count = api_cl.list_findings(asset_id=asset_id).json()["total"]
        assert reported_count == actual_count == len(vuln_ids)


class TestAssetPagination:
    @pytest.mark.xfail(
        strict=True,
        reason="Scanner Service pagination skips the first asset — id=1 (prod-web-01) never appears on page 1",
    )
    def test_first_page_includes_first_asset(self, scanner_cl: ScannerClient):
        """Title: First page should include the first asset.

            Steps:
            1. Request assets with page=1 and per_page=10.
            2. Extract asset IDs from response.
            3. Assert asset with id=1 is present in results.
            """
        resp = scanner_cl.list_assets(page=1, per_page=10)
        assert resp.status_code == 200
        body = resp.json()
        ids = [a["id"] for a in body["items"]]
        assert 1 in ids, (
            f"Asset id=1 (prod-web-01) is missing from page 1. Got ids: {ids}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="Scanner Service pagination off-by-one: items count does not match reported total",
    )
    def test_items_count_matches_total_on_single_page(self, scanner_cl: ScannerClient):
        """Title: Items count matches total when all assets fit on one page.

        Steps:
        1. Request assets with large per_page value.
        2. Compare length of items with total field.
        3. Assert both values are equal.
        """
        resp = scanner_cl.list_assets(page=1, per_page=100)
        body = resp.json()
        assert len(body["items"]) == body["total"], (
            f"total={body['total']} but got {len(body['items'])} items"
        )

    def test_hostname_present_in_listed_assets(self, scanner_cl: ScannerClient):
        """Title: Known hostnames appear in asset list.

        Steps:
        1. Request first page of assets.
        2. Extract hostnames from response.
        3. Assert at least one known hostname is present.
        """
        body = scanner_cl.list_assets(page=1, per_page=10).json()
        hostnames = {a["hostname"] for a in body["items"]}
        assert "prod-web-01" in hostnames or "prod-web-02" in hostnames


class TestDuplicateFindings:
    @pytest.mark.xfail(
        strict=True,
        reason="Scanner Service creates duplicate findings when the same scan is submitted twice for the same asset+vulnerability",
    )
    def test_running_same_scan_twice_does_not_create_duplicates(
        self, scanner_cl: ScannerClient, api_cl: DashboardClient, created_asset
    ):
        """Title: Running identical scans should not create duplicate findings.

        Steps:
        1. Run a scan for a given asset and vulnerability.
        2. Run the same scan again.
        3. Query Dashboard API for findings for that asset.
        4. Filter findings by vulnerability_id.
        5. Assert only one finding exists.
        """
        asset_id = created_asset["id"]
        vuln_ids = [1]

        scanner_cl.create_scan(asset_id, "pytest-scanner", vuln_ids)
        scanner_cl.create_scan(asset_id, "pytest-scanner", vuln_ids)

        findings = api_cl.list_findings(asset_id=asset_id).json()["items"]
        dupes = [
            f for f in findings
            if f["vulnerability_id"] == vuln_ids[0]
        ]
        assert len(dupes) == 1, (
            f"Expected 1 finding for vuln {vuln_ids[0]} on asset {asset_id}, "
            f"got {len(dupes)} duplicates"
        )


class TestStatusUpdateCrossService:
    def test_status_update_reflected_in_db(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: Status update via API is reflected in database.

        Steps:
        1. Update finding status via Dashboard API.
        2. Query database for the same finding.
        3. Assert status and notes match API input.
        """
        finding_id = created_finding["id"]
        api_cl.update_finding_status_by_id(finding_id, "in_progress", notes="cross-service check")

        db.execute("SELECT status, notes FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["status"] == "in_progress"
        assert row["notes"] == "cross-service check"

    def test_scan_then_update_status_then_verify_db(
        self, scanner_cl: ScannerClient, api_cl: DashboardClient, created_asset, db
    ):
        """Title: Scan followed by status update is persisted in DB.

        Steps:
        1. Run a scan to create findings.
        2. Retrieve a finding via Dashboard API.
        3. Update finding status via API.
        4. Query database for that finding.
        5. Assert status is updated.
        """
        asset_id = created_asset["id"]
        scanner_cl.create_scan(asset_id, "pytest-scanner", [6])

        findings = api_cl.list_findings(asset_id=asset_id).json()["items"]
        assert len(findings) >= 1
        finding_id = findings[0]["id"]

        api_cl.update_finding_status_by_id(finding_id, "confirmed")

        db.execute("SELECT status FROM findings WHERE id = %s", (finding_id,))
        assert db.fetchone()["status"] == "confirmed"

#TODO: Add concurrency by Threading
# class TestConcurrentScans:
#     def test_concurrent_scans_do_not_create_duplicate_findings(
#         self, scanner_cl: ScannerClient, api_cl: DashboardClient, created_asset
#     ):
#         """Title: Concurrent scans for the same asset+vulnerability produce exactly one finding.
#
#         Steps:
#         1. Create a temporary asset via fixture.
#         2. Submit 3 identical scans concurrently using threads.
#         3. Collect all HTTP responses and assert each returned 201.
#         4. Query the Dashboard API for findings on that asset.
#         5. Assert exactly one finding exists for the target vulnerability.
#         """