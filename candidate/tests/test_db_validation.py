import pytest
import psycopg2
from clients.dashboard_client import DashboardClient


class TestDismissalPersistence:
    def test_dismiss_via_api_sets_flag_in_db(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: Dismissing a finding via API sets is_dismissed=TRUE in DB.

        Steps:
        1. Create a finding via fixture.
        2. Call dismiss endpoint for the finding.
        3. Query the DB directly for is_dismissed.
        4. Assert the flag is TRUE.
        """
        finding_id = created_finding["id"]
        api_cl.dismiss_finding_by_id(finding_id)

        db.execute(
            "SELECT is_dismissed FROM findings WHERE id = %s", (finding_id,)
        )
        row = db.fetchone()
        assert row is not None
        assert row["is_dismissed"] is True

    def test_dismissed_finding_excluded_from_list_but_exists_in_db(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: Dismissed finding is hidden from API list but retained in DB (soft delete).

        Steps:
        1. Create a finding via fixture.
        2. Dismiss the finding via API.
        3. Assert the finding ID is absent from the API list response.
        4. Query the DB directly and assert the row still exists.
        """
        finding_id = created_finding["id"]
        api_cl.dismiss_finding_by_id(finding_id)

        # API should not return it
        all_ids = {f["id"] for f in api_cl.list_findings().json()["items"]}
        assert finding_id not in all_ids

        # But the row must still exist in the DB (soft delete)
        db.execute("SELECT id FROM findings WHERE id = %s", (finding_id,))
        assert db.fetchone() is not None


class TestCreationPersistence:
    def test_detected_at_set_on_creation(self, api_cl: DashboardClient, created_finding, db):
        """Title: New finding has detected_at populated automatically on creation.

        Steps:
        1. Create a finding via fixture.
        2. Query detected_at from DB for the new finding.
        3. Assert detected_at is not NULL.
        """
        db.execute("SELECT detected_at FROM findings WHERE id = %s", (created_finding["id"],))
        row = db.fetchone()
        assert row["detected_at"] is not None

    def test_is_dismissed_false_on_creation(self, api_cl: DashboardClient, created_finding, db):
        """Title: New finding has is_dismissed=FALSE by default on creation.

        Steps:
        1. Create a finding via fixture.
        2. Query is_dismissed from DB for the new finding.
        3. Assert the flag is FALSE.
        """
        db.execute("SELECT is_dismissed FROM findings WHERE id = %s", (created_finding["id"],))
        row = db.fetchone()
        assert row["is_dismissed"] is False


class TestStatusPersistence:
    def test_status_update_persists_to_db(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: Status update via API is persisted to the DB.

        Steps:
        1. Create a finding via fixture.
        2. Update status to 'confirmed' via API.
        3. Query the DB for the finding's status.
        4. Assert status equals 'confirmed'.
        """
        finding_id = created_finding["id"]
        api_cl.update_finding_status_by_id(finding_id, "confirmed")

        db.execute("SELECT status FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["status"] == "confirmed"

    def test_resolved_at_set_when_status_is_resolved(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: resolved_at timestamp is set in DB when status is changed to 'resolved'.

        Steps:
        1. Create a finding via fixture.
        2. Update status to 'resolved' via API.
        3. Query resolved_at from the DB.
        4. Assert resolved_at is not NULL.
        """
        finding_id = created_finding["id"]
        api_cl.update_finding_status_by_id(finding_id, "resolved")

        db.execute("SELECT resolved_at FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["resolved_at"] is not None

    def test_resolved_at_cleared_when_status_changes_from_resolved(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: resolved_at is cleared in DB when status changes away from 'resolved'.

        Steps:
        1. Create a finding via fixture.
        2. Update status to 'resolved' via API.
        3. Update status to 'in_progress' via API.
        4. Query resolved_at from the DB.
        5. Assert resolved_at is NULL.
        """
        finding_id = created_finding["id"]
        api_cl.update_finding_status_by_id(finding_id, "resolved")
        api_cl.update_finding_status_by_id(finding_id, "in_progress")

        db.execute("SELECT resolved_at FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["resolved_at"] is None

    def test_notes_persist_after_api_update(
        self, api_cl: DashboardClient, created_finding, db
    ):
        """Title: Notes provided in status update request are persisted to the DB.

        Steps:
        1. Create a finding via fixture.
        2. Update status to 'confirmed' with notes='persisted note' via API.
        3. Query notes from the DB.
        4. Assert notes equal 'persisted note'.
        """
        finding_id = created_finding["id"]
        api_cl.update_finding_status_by_id(finding_id, "confirmed", notes="persisted note")

        db.execute("SELECT notes FROM findings WHERE id = %s", (finding_id,))
        row = db.fetchone()
        assert row["notes"] == "persisted note"


class TestDatabaseConstraints:
    @pytest.mark.xfail(
        strict=True,
        reason="Missing CHECK constraint on vulnerabilities.cvss_score — DB accepts values outside [0, 10]",
    )
    def test_cvss_score_out_of_range_rejected_by_db(self, db_client):
        """Title: DB rejects CVSS scores outside the valid range [0, 10].

        Steps:
        1. Attempt to insert a vulnerability with cvss_score=15.0 directly into the DB.
        2. Assert a CheckViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO vulnerabilities (cve_id, title, severity, cvss_score)
                VALUES (%s, %s, %s, %s)
                """,
                ("CVE-9999-00001", "Test vuln out-of-range CVSS", "high", 15.0),
            )
            db_client.commit()
            # Clean up
            cursor.execute("DELETE FROM vulnerabilities WHERE cve_id = 'CVE-9999-00001'")
            db_client.commit()
            pytest.fail(
                "DB accepted CVSS score of 15.0 — missing CHECK constraint on cvss_score"
            )
        except psycopg2.errors.CheckViolation:
            db_client.rollback()  # constraint worked correctly
        finally:
            cursor.close()

    def test_finding_requires_valid_asset_fk(self, db_client):
        """Title: DB rejects a finding that references a non-existent asset (FK constraint).

        Steps:
        1. Attempt to insert a finding with asset_id=999999 directly into the DB.
        2. Assert a ForeignKeyViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (999999, 1, 'open')
                """
            )
            db_client.commit()
            cursor.execute("DELETE FROM findings WHERE asset_id = 999999")
            db_client.commit()
            pytest.fail("FK constraint on findings.asset_id not enforced")
        except psycopg2.errors.ForeignKeyViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_finding_requires_valid_vulnerability_fk(self, db_client):
        """Title: DB rejects a finding that references a non-existent vulnerability (FK constraint).

        Steps:
        1. Attempt to insert a finding with vulnerability_id=999999 directly into the DB.
        2. Assert a ForeignKeyViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (1, 999999, 'open')
                """
            )
            db_client.commit()
            cursor.execute("DELETE FROM findings WHERE vulnerability_id = 999999")
            db_client.commit()
            pytest.fail("FK constraint on findings.vulnerability_id not enforced")
        except psycopg2.errors.ForeignKeyViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_vulnerability_cve_id_is_unique(self, db_client):
        """Title: DB enforces uniqueness on vulnerabilities.cve_id.

        Steps:
        1. Attempt to insert a vulnerability with a CVE ID that already exists in seed data.
        2. Assert a UniqueViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO vulnerabilities (cve_id, title, severity)
                VALUES ('CVE-2021-44228', 'Duplicate Log4Shell', 'critical')
                """
            )
            db_client.commit()
            pytest.fail("Unique constraint on vulnerabilities.cve_id not enforced")
        except psycopg2.errors.UniqueViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_asset_hostname_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on assets.hostname.

        Steps:
        1. Attempt to insert an asset with hostname=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO assets (hostname, asset_type, environment)
                VALUES (NULL, 'server', 'production')
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on assets.hostname not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_asset_type_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on assets.asset_type.

        Steps:
        1. Attempt to insert an asset with asset_type=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO assets (hostname, asset_type, environment)
                VALUES ('test-no-type', NULL, 'production')
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on assets.asset_type not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_asset_environment_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on assets.environment.

        Steps:
        1. Attempt to insert an asset with environment=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO assets (hostname, asset_type, environment)
                VALUES ('test-no-env', 'server', NULL)
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on assets.environment not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_scan_requires_valid_asset_fk(self, db_client):
        """Title: DB rejects a scan that references a non-existent asset (FK constraint).

        Steps:
        1. Attempt to insert a scan with asset_id=999999 directly into the DB.
        2. Assert a ForeignKeyViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO scans (asset_id, scanner_name, status)
                VALUES (999999, 'pytest-scanner', 'completed')
                """
            )
            db_client.commit()
            cursor.execute("DELETE FROM scans WHERE asset_id = 999999")
            db_client.commit()
            pytest.fail("FK constraint on scans.asset_id not enforced")
        except psycopg2.errors.ForeignKeyViolation:
            db_client.rollback()
        finally:
            cursor.close()

    @pytest.mark.xfail(
        strict=True,
        reason="Missing CHECK/ENUM constraint on findings.status — DB accepts arbitrary string values",
    )
    def test_finding_invalid_status_rejected_by_db(self, db_client):
        """Title: DB rejects a finding with an invalid status value.

        Steps:
        1. Attempt to insert a finding with status='invalid' directly into the DB.
        2. Assert a CheckViolation (or similar) exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (1, 1, 'invalid')
                """
            )
            db_client.commit()
            cursor.execute("DELETE FROM findings WHERE asset_id = 1 AND vulnerability_id = 1 AND status = 'invalid'")
            db_client.commit()
            pytest.fail("CHECK/ENUM constraint on findings.status not enforced")
        except (psycopg2.errors.CheckViolation, psycopg2.errors.InvalidTextRepresentation):
            db_client.rollback()
        finally:
            cursor.close()

    @pytest.mark.xfail(
        strict=True,
        reason="Missing CHECK/ENUM constraint on vulnerabilities.severity — DB accepts arbitrary string values",
    )
    def test_vulnerability_invalid_severity_rejected_by_db(self, db_client):
        """Title: DB rejects a vulnerability with an invalid severity value.

        Steps:
        1. Attempt to insert a vulnerability with severity='extreme' directly into the DB.
        2. Assert a CheckViolation (or similar) exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO vulnerabilities (cve_id, title, severity)
                VALUES ('CVE-9999-00002', 'Test invalid severity', 'extreme')
                """
            )
            db_client.commit()
            cursor.execute("DELETE FROM vulnerabilities WHERE cve_id = 'CVE-9999-00002'")
            db_client.commit()
            pytest.fail("CHECK/ENUM constraint on vulnerabilities.severity not enforced")
        except (psycopg2.errors.CheckViolation, psycopg2.errors.InvalidTextRepresentation):
            db_client.rollback()
        finally:
            cursor.close()

    def test_finding_status_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on findings.status.

        Steps:
        1. Attempt to insert a finding with status=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (1, 1, NULL)
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on findings.status not enforced")
        except (psycopg2.errors.NotNullViolation, psycopg2.errors.InvalidTextRepresentation):
            db_client.rollback()
        finally:
            cursor.close()

    def test_finding_asset_id_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on findings.asset_id.

        Steps:
        1. Attempt to insert a finding with asset_id=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (NULL, 1, 'open')
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on findings.asset_id not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_finding_vulnerability_id_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on findings.vulnerability_id.

        Steps:
        1. Attempt to insert a finding with vulnerability_id=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO findings (asset_id, vulnerability_id, status)
                VALUES (1, NULL, 'open')
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on findings.vulnerability_id not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_vulnerability_cve_id_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on vulnerabilities.cve_id.

        Steps:
        1. Attempt to insert a vulnerability with cve_id=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO vulnerabilities (cve_id, title, severity)
                VALUES (NULL, 'Test no CVE', 'high')
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on vulnerabilities.cve_id not enforced")
        except psycopg2.errors.NotNullViolation:
            db_client.rollback()
        finally:
            cursor.close()

    def test_vulnerability_severity_is_required(self, db_client):
        """Title: DB enforces NOT NULL constraint on vulnerabilities.severity.

        Steps:
        1. Attempt to insert a vulnerability with severity=NULL directly into the DB.
        2. Assert a NotNullViolation exception is raised.
        3. Rollback on success; fail the test if the insert was accepted.
        """
        cursor = db_client.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO vulnerabilities (cve_id, title, severity)
                VALUES ('CVE-9999-00003', 'Test no severity', NULL)
                """
            )
            db_client.commit()
            pytest.fail("NOT NULL constraint on vulnerabilities.severity not enforced")
        except (psycopg2.errors.NotNullViolation, psycopg2.errors.InvalidTextRepresentation):
            db_client.rollback()
        finally:
            cursor.close()


class TestDataConsistency:
    def test_all_findings_reference_existing_assets(self, db):
        """Title: No finding in the DB references a non-existent asset (data integrity check).

        Steps:
        1. Query all findings that have no matching asset via LEFT JOIN.
        2. Assert the result set is empty.
        """
        db.execute(
            """
            SELECT f.id
            FROM findings f
            LEFT JOIN assets a ON f.asset_id = a.id
            WHERE a.id IS NULL
            """
        )
        orphans = db.fetchall()
        assert len(orphans) == 0, f"Orphaned findings (no asset): {orphans}"

    def test_all_findings_reference_existing_vulnerabilities(self, db):
        """Title: No finding in the DB references a non-existent vulnerability (data integrity check).

        Steps:
        1. Query all findings that have no matching vulnerability via LEFT JOIN.
        2. Assert the result set is empty.
        """
        db.execute(
            """
            SELECT f.id
            FROM findings f
            LEFT JOIN vulnerabilities v ON f.vulnerability_id = v.id
            WHERE v.id IS NULL
            """
        )
        orphans = db.fetchall()
        assert len(orphans) == 0, f"Orphaned findings (no vulnerability): {orphans}"

    def test_finding_statuses_are_valid_enum_values(self, db):
        """Title: All status values stored in findings match the defined enum set.

        Steps:
        1. Query all distinct status values from the findings table.
        2. Assert every value belongs to the known valid set.
        """
        valid = {"open", "confirmed", "in_progress", "resolved", "false_positive"}
        db.execute("SELECT DISTINCT status FROM findings")
        db_statuses = {row["status"] for row in db.fetchall()}
        invalid = db_statuses - valid
        assert not invalid, f"Invalid status values in DB: {invalid}"

    def test_cvss_scores_in_valid_range(self, db):
        """Title: All CVSS scores stored in vulnerabilities are within the valid range [0, 10].

        Steps:
        1. Query all vulnerabilities where cvss_score < 0 or cvss_score > 10.
        2. Assert the result set is empty.
        """
        db.execute(
            "SELECT cve_id, cvss_score FROM vulnerabilities WHERE cvss_score < 0 OR cvss_score > 10"
        )
        bad = db.fetchall()
        assert len(bad) == 0, f"CVSS scores out of range [0,10]: {bad}"

    def test_resolved_findings_have_resolved_at_timestamp(self, db):
        """Title: All findings with status='resolved' have a non-NULL resolved_at timestamp.

        Steps:
        1. Query all findings where status='resolved' and resolved_at IS NULL.
        2. Assert the result set is empty.
        """
        db.execute(
            "SELECT id FROM findings WHERE status = 'resolved' AND resolved_at IS NULL"
        )
        bad = db.fetchall()
        assert len(bad) == 0, f"Resolved findings missing resolved_at: {[r['id'] for r in bad]}"
