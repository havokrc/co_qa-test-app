import pytest
from clients.dashboard_client import DashboardClient
from clients.scanner_client import ScannerClient
from services.finding_actions import FindingActions


class TestDismissalPersistence:
    def test_dismiss_via_api_sets_flag_in_db(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: Dismissing a finding via API sets is_dismissed=TRUE in DB.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send DELETE /findings/{id} to dismiss it.
        3. Check the database for is_dismissed of that finding.
        4. Assert the flag is TRUE.
        """
        finding_id = created_finding["id"]
        finding_actions.dismiss(finding_id)

        db.execute(
            "SELECT is_dismissed FROM findings WHERE id = %s", (finding_id,)
        )
        row = db.fetchone()
        assert row is not None
        assert row["is_dismissed"] is True

    def test_dismissed_finding_excluded_from_list_but_exists_in_db(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions, created_finding, db
    ):
        """Title: Dismissed finding is hidden from API list but retained in DB (soft delete).

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send DELETE /findings/{id} to dismiss it.
        3. Assert the finding ID is absent from GET /findings list filtered by asset_id.
        4. Check the database and assert the row still exists.
        """
        finding_id = created_finding["id"]
        finding_actions.dismiss(finding_id)

        resp = dashboard_api_cl.list_findings(asset_id=created_finding["asset_id"], per_page=100)
        assert resp.status_code == 200
        all_ids = {f["id"] for f in resp.json()["items"]}
        assert finding_id not in all_ids

        db.execute("SELECT id FROM findings WHERE id = %s", (finding_id,))
        assert db.fetchone() is not None

    def test_dismissed_finding_retains_original_data_in_db(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: Dismissing a finding does not alter its original data in DB.

        Steps:
        1. Send POST /findings to create a new finding and note its original notes and status.
        2. Send DELETE /findings/{id} to dismiss it.
        3. Check the database for the finding's notes, status, and detected_at.
        4. Assert none of the original fields were modified.
        """
        finding_id = created_finding["id"]
        original_notes = created_finding["notes"]
        original_status = created_finding["status"]

        finding_actions.dismiss(finding_id)

        db.execute(
            "SELECT status, notes, detected_at FROM findings WHERE id = %s", (finding_id,)
        )
        row = db.fetchone()
        assert row["status"] == original_status
        assert row["notes"] == original_notes
        assert row["detected_at"] is not None


class TestCreationPersistence:
    def test_detected_at_set_on_creation(self, created_finding, db):
        """Title: New finding has detected_at populated automatically on creation.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Check the database for detected_at of that finding.
        3. Assert detected_at is not NULL.
        """
        db.execute("SELECT detected_at FROM findings WHERE id = %s", (created_finding["id"],))
        row = db.fetchone()
        assert row["detected_at"] is not None

    def test_is_dismissed_false_on_creation(self, created_finding, db):
        """Title: New finding has is_dismissed=FALSE by default on creation.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Check the database for is_dismissed of that finding.
        3. Assert the flag is FALSE.
        """
        db.execute("SELECT is_dismissed FROM findings WHERE id = %s", (created_finding["id"],))
        row = db.fetchone()
        assert row["is_dismissed"] is False

    def test_detected_at_not_modified_on_status_change(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: detected_at timestamp is immutable — not changed by status updates.

        Steps:
        1. Send POST /findings to create a new finding and read detected_at from the database.
        2. Send PUT /findings/{id}/status with status='confirmed'.
        3. Check the database for detected_at of that finding again.
        4. Assert detected_at is unchanged.
        """
        finding_id = created_finding["id"]
        db.execute("SELECT detected_at FROM findings WHERE id = %s", (finding_id,))
        original_detected_at = db.fetchone()["detected_at"]

        finding_actions.update_status(finding_id, "confirmed")

        db.execute("SELECT detected_at FROM findings WHERE id = %s", (finding_id,))
        assert db.fetchone()["detected_at"] == original_detected_at


class TestStatusPersistence:
    def test_status_update_persists_to_db(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: Status update via API is persisted to the DB.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='confirmed'.
        3. Check the database for the status of that finding.
        4. Assert status equals 'confirmed'.
        """
        finding_id = created_finding["id"]
        finding_actions.update_status(finding_id, "confirmed")

        db.execute("SELECT status FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["status"] == "confirmed"

    def test_resolved_at_set_when_status_is_resolved(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: resolved_at timestamp is set in DB when status is changed to 'resolved'.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='resolved'.
        3. Check the database for resolved_at of that finding.
        4. Assert resolved_at is not NULL.
        """
        finding_id = created_finding["id"]
        finding_actions.update_status(finding_id, "resolved")

        db.execute("SELECT resolved_at FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["resolved_at"] is not None

    def test_resolved_at_cleared_when_status_changes_from_resolved(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: resolved_at is cleared in DB when status changes away from 'resolved'.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='resolved'.
        3. Send PUT /findings/{id}/status with status='in_progress'.
        4. Check the database for resolved_at of that finding.
        5. Assert resolved_at is NULL.
        """
        finding_id = created_finding["id"]
        finding_actions.update_status(finding_id, "resolved")
        finding_actions.update_status(finding_id, "in_progress")

        db.execute("SELECT resolved_at FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["resolved_at"] is None

    def test_notes_persist_after_api_update(
        self, finding_actions: FindingActions, created_finding, db
    ):
        """Title: Notes provided in status update request are persisted to the DB.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='confirmed' and notes='persisted note'.
        3. Check the database for notes of that finding.
        4. Assert notes equal 'persisted note'.
        """
        finding_id = created_finding["id"]
        finding_actions.update_status(finding_id, "confirmed", notes="persisted note")

        db.execute("SELECT notes FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["notes"] == "persisted note"


class TestScanIntegrity:
    def test_scan_findings_count_matches_db_rows(
        self, scanner_api_cl: ScannerClient, created_asset, valid_vulnerability_ids, db
    ):
        """Title: Scan findings_count matches actual rows inserted in DB.

        Steps:
        1. Send POST /scans for a valid asset with 2 known vulnerability IDs.
        2. Capture findings_count from the scan response.
        3. Check the database: COUNT(*) of findings rows for that asset.
        4. Assert the reported count equals the actual DB row count.
        """
        asset_id = created_asset["id"]
        vuln_ids = valid_vulnerability_ids[:2]

        resp = scanner_api_cl.create_scan(asset_id, "pytest-scanner", vuln_ids)
        assert resp.status_code == 201
        reported_count = resp.json()["findings_count"]

        db.execute("SELECT COUNT(*) as cnt FROM findings WHERE asset_id = %s", (asset_id,))
        actual_count = db.fetchone()["cnt"]

        assert reported_count == actual_count == len(vuln_ids)


    def test_scan_findings_have_correct_vulnerability_ids_in_db(
        self, scanner_api_cl: ScannerClient, created_asset, valid_vulnerability_ids, db
    ):
        """Title: Vulnerability IDs in DB match those submitted in scan request.

        Steps:
        1. Send POST /scans for a valid asset with 3 specific vulnerability IDs.
        2. Check the database for vulnerability_id values on findings for that asset.
        3. Assert the set of IDs matches the submitted set.
        """
        asset_id = created_asset["id"]
        vuln_ids = valid_vulnerability_ids[:3]

        resp = scanner_api_cl.create_scan(asset_id, "pytest-scanner", vuln_ids)
        assert resp.status_code == 201

        db.execute(
            "SELECT vulnerability_id FROM findings WHERE asset_id = %s", (asset_id,)
        )
        rows = db.fetchall()
        assert len(rows) == len(vuln_ids)
        assert {row["vulnerability_id"] for row in rows} == set(vuln_ids)


class TestDataIntegrity:
    VALID_SEVERITIES = {"critical", "high", "medium", "low"}
    VALID_STATUSES = {"open", "confirmed", "in_progress", "resolved", "false_positive"}

    def test_no_orphaned_finding_asset_ids(self, db):
        """Title: All findings.asset_id values reference an existing asset row.

        Steps:
        1. Check the database for findings whose asset_id has no matching row in the assets table.
        2. Assert no such findings exist.
        """
        db.execute("""
            SELECT f.id
            FROM findings f
            LEFT JOIN assets a ON f.asset_id = a.id
            WHERE a.id IS NULL
        """)
        orphaned = db.fetchall()
        assert len(orphaned) == 0, (
            f"Found {len(orphaned)} finding(s) with orphaned asset_id: "
            f"{[r['id'] for r in orphaned]}"
        )

    def test_no_orphaned_finding_vulnerability_ids(self, db):
        """Title: All findings.vulnerability_id values reference an existing vulnerability row.

        Steps:
        1. Check the database for findings whose vulnerability_id has no matching row in the vulnerabilities table.
        2. Assert no such findings exist.
        """
        db.execute("""
            SELECT f.id
            FROM findings f
            LEFT JOIN vulnerabilities v ON f.vulnerability_id = v.id
            WHERE v.id IS NULL
        """)
        orphaned = db.fetchall()
        assert len(orphaned) == 0, (
            f"Found {len(orphaned)} finding(s) with orphaned vulnerability_id: "
            f"{[r['id'] for r in orphaned]}"
        )

    def test_all_cvss_scores_within_valid_range(self, db):
        """Title: All non-null CVSS scores in vulnerabilities are within the valid 0.0–10.0 range.

        Steps:
        1. Check the database for vulnerabilities where cvss_score is set but falls outside 0.0–10.0.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id, cve_id, cvss_score
            FROM vulnerabilities
            WHERE cvss_score IS NOT NULL
              AND (cvss_score < 0.0 OR cvss_score > 10.0)
        """)
        out_of_range = db.fetchall()
        assert len(out_of_range) == 0, (
            f"Found {len(out_of_range)} vulnerability/ies with out-of-range CVSS: "
            f"{[(r['cve_id'], r['cvss_score']) for r in out_of_range]}"
        )

    def test_all_vulnerability_severity_values_are_valid(self, db):
        """Title: All severity values in vulnerabilities belong to the allowed set.

        Steps:
        1. Check the database for all distinct severity values in the vulnerabilities table.
        2. Assert every value is one of: critical, high, medium, low.
        """
        db.execute("SELECT DISTINCT severity FROM vulnerabilities")
        rows = db.fetchall()
        db_severities = {r["severity"] for r in rows}
        invalid = db_severities - self.VALID_SEVERITIES
        assert not invalid, f"Invalid severity values found in DB: {invalid}"

    def test_all_finding_status_values_are_valid(self, db):
        """Title: All status values in findings belong to the allowed set.

        Steps:
        1. Check the database for all distinct status values in the findings table.
        2. Assert every value is one of: open, confirmed, in_progress, resolved, false_positive.
        """
        db.execute("SELECT DISTINCT status FROM findings")
        rows = db.fetchall()
        db_statuses = {r["status"] for r in rows}
        invalid = db_statuses - self.VALID_STATUSES
        assert not invalid, f"Invalid status values found in DB: {invalid}"

    def test_cve_ids_are_unique(self, db):
        """Title: All CVE IDs in the vulnerabilities table are unique.

        Steps:
        1. Check the database for cve_id values that appear more than once in the vulnerabilities table.
        2. Assert no duplicates exist.
        """
        db.execute("""
            SELECT cve_id, COUNT(*) as cnt
            FROM vulnerabilities
            GROUP BY cve_id
            HAVING COUNT(*) > 1
        """)
        duplicates = db.fetchall()
        assert len(duplicates) == 0, (
            f"Duplicate CVE IDs found: {[(r['cve_id'], r['cnt']) for r in duplicates]}"
        )


class TestTimestampConsistency:
    """Cross-field timestamp logic — verifies temporal invariants across the findings table."""

    def test_non_resolved_findings_have_null_resolved_at(self, db):
        """Title: resolved_at is NULL for all findings whose status is not 'resolved'.

        Steps:
        1. Check the database for findings where status is not 'resolved' but resolved_at is set.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id, status, resolved_at
            FROM findings
            WHERE status != 'resolved'
              AND resolved_at IS NOT NULL
        """)
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} finding(s) with resolved_at set but status != 'resolved': "
            f"{[(r['id'], r['status']) for r in rows]}"
        )

    def test_resolved_findings_have_non_null_resolved_at(self, db):
        """Title: resolved_at is NOT NULL for all findings with status='resolved'.

        Steps:
        1. Check the database for findings where status is 'resolved' but resolved_at is NULL.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id FROM findings
            WHERE status = 'resolved'
              AND resolved_at IS NULL
        """)
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} finding(s) with status='resolved' but NULL resolved_at: "
            f"{[r['id'] for r in rows]}"
        )

    def test_resolved_at_is_after_detected_at(self, db):
        """Title: resolved_at is chronologically after detected_at for all resolved findings.

        Steps:
        1. Check the database for resolved findings where resolved_at is earlier than detected_at.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id, detected_at, resolved_at
            FROM findings
            WHERE resolved_at IS NOT NULL
              AND resolved_at < detected_at
        """)
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} finding(s) where resolved_at precedes detected_at: "
            f"{[(r['id'], str(r['detected_at']), str(r['resolved_at'])) for r in rows]}"
        )

    def test_scan_completed_at_set_when_status_is_completed(self, db):
        """Title: completed_at is NOT NULL for all scans with status='completed'.

        Steps:
        1. Check the database for scans where status is 'completed' but completed_at is NULL.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id FROM scans
            WHERE status = 'completed'
              AND completed_at IS NULL
        """)
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} completed scan(s) with NULL completed_at: "
            f"{[r['id'] for r in rows]}"
        )

    def test_scan_completed_at_after_started_at(self, db):
        """Title: completed_at is chronologically after started_at for all completed scans.

        Steps:
        1. Check the database for scans where completed_at is set but earlier than started_at.
        2. Assert no such rows exist.
        """
        db.execute("""
            SELECT id, started_at, completed_at
            FROM scans
            WHERE completed_at IS NOT NULL
              AND completed_at < started_at
        """)
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} scan(s) where completed_at precedes started_at: "
            f"{[(r['id'], str(r['started_at']), str(r['completed_at'])) for r in rows]}"
        )


class TestScanConsistency:
    """Scan-level cross-table integrity checks."""

    VALID_SCAN_STATUSES = {"running", "completed"}

    def test_no_orphaned_scan_asset_ids(self, db):
        """Title: All scans.asset_id values reference an existing asset row.

        Steps:
        1. Check the database for scans whose asset_id has no matching row in the assets table.
        2. Assert no such scans exist.
        """
        db.execute("""
            SELECT s.id
            FROM scans s
            LEFT JOIN assets a ON s.asset_id = a.id
            WHERE a.id IS NULL
        """)
        orphaned = db.fetchall()
        assert len(orphaned) == 0, (
            f"Found {len(orphaned)} scan(s) with orphaned asset_id: "
            f"{[r['id'] for r in orphaned]}"
        )

    def test_scan_status_values_are_valid(self, db):
        """Title: All status values in the scans table belong to the allowed set.

        Steps:
        1. Check the database for all distinct status values in the scans table.
        2. Assert every value is one of: running, completed.
        """
        db.execute("SELECT DISTINCT status FROM scans")
        rows = db.fetchall()
        db_statuses = {r["status"] for r in rows}
        invalid = db_statuses - self.VALID_SCAN_STATUSES
        assert not invalid, f"Invalid scan status values found in DB: {invalid}"

    def test_scan_scanner_name_persisted_to_db(
        self, scanner_api_cl: ScannerClient, created_asset, valid_vulnerability_ids, db
    ):
        """Title: scanner_name from scan request is persisted correctly in the scans table.

        Steps:
        1. Send POST /scans with a specific scanner_name.
        2. Check the database for the scans row matching the returned scan ID.
        3. Assert scanner_name in the database matches the submitted value.
        """
        asset_id = created_asset["id"]
        scanner_name = "pytest-name-check"

        resp = scanner_api_cl.create_scan(asset_id, scanner_name, valid_vulnerability_ids[:1])
        assert resp.status_code == 201
        scan_id = resp.json()["id"]

        db.execute("SELECT scanner_name FROM scans WHERE id = %s", (scan_id,))
        row = db.fetchone()
        assert row is not None
        assert row["scanner_name"] == scanner_name

    def test_scan_scanner_name_propagated_to_findings(
        self, scanner_api_cl: ScannerClient, created_asset, valid_vulnerability_ids, db
    ):
        """Title: scanner_name from scan is propagated as scanner field in created findings.

        Steps:
        1. Send POST /scans with a specific scanner_name for a unique asset.
        2. Check the database for all findings created for that asset.
        3. Assert every finding has the scanner field equal to the scanner_name.
        """
        asset_id = created_asset["id"]
        scanner_name = "pytest-propagation-check"
        vuln_ids = valid_vulnerability_ids[:2]

        resp = scanner_api_cl.create_scan(asset_id, scanner_name, vuln_ids)
        assert resp.status_code == 201

        db.execute(
            "SELECT scanner FROM findings WHERE asset_id = %s", (asset_id,)
        )
        rows = db.fetchall()
        assert len(rows) == len(vuln_ids)
        assert all(r["scanner"] == scanner_name for r in rows), (
            f"Not all findings have scanner='{scanner_name}': "
            f"{[r['scanner'] for r in rows]}"
        )

    def test_scan_findings_count_is_non_negative(self, db):
        """Title: findings_count is non-negative for all scans.

        Steps:
        1. Check the database for scans where findings_count is negative.
        2. Assert no such rows exist.
        """
        db.execute("SELECT id, findings_count FROM scans WHERE findings_count < 0")
        rows = db.fetchall()
        assert len(rows) == 0, (
            f"Found {len(rows)} scan(s) with negative findings_count: "
            f"{[(r['id'], r['findings_count']) for r in rows]}"
        )
