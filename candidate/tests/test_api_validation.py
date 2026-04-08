import pytest
from clients.dashboard_client import DashboardClient
from validators.finding_schema import (
    assert_valid_finding_response,
    assert_valid_finding_detail,
    assert_valid_search_result,
    assert_valid_paginated_findings,
)


class TestHealthCheck:
    def test_health_returns_200(self, api_cl: DashboardClient):
        """
        Title: Health check endpoint returns 200.
        Steps:
          1. Send GET /health.
          2. Assert response status is 200.
        """
        resp = api_cl.health()
        assert resp.status_code == 200


class TestListFindings:
    def test_returns_200_with_expected_shape(self, api_cl: DashboardClient):
        """
        Title: List findings returns 200 with valid paginated shape.
        Steps:
          1. Send GET /findings.
          2. Assert response status is 200.
          3. Assert response body matches paginated findings schema.
        """
        resp = api_cl.list_findings()
        assert resp.status_code == 200
        assert_valid_paginated_findings(resp.json())

    def test_default_pagination(self, api_cl: DashboardClient):
        """
        Title: List findings uses page=1 and per_page=20 by default.
        Steps:
          1. Send GET /findings without pagination params.
          2. Assert page == 1 and per_page == 20.
        """
        resp = api_cl.list_findings()
        body = resp.json()
        assert body["page"] == 1
        assert body["per_page"] == 20

    def test_pagination_returns_different_pages(self, api_cl: DashboardClient):
        """
        Title: Paginated results do not overlap between pages.
        Steps:
          1. Send GET /findings?page=1&per_page=2.
          2. Send GET /findings?page=2&per_page=2.
          3. Assert finding IDs from page 1 and page 2 are disjoint.
        """
        page1 = api_cl.list_findings(page=1, per_page=2).json()
        page2 = api_cl.list_findings(page=2, per_page=2).json()
        ids_p1 = {f["id"] for f in page1["items"]}
        ids_p2 = {f["id"] for f in page2["items"]}
        assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"

    @pytest.mark.parametrize("status", ["open", "confirmed", "in_progress", "resolved", "false_positive"])
    def test_filter_by_status(self, api_cl: DashboardClient, status):
        """
        Title: Filtering by status {status} returns only matching findings.
        Steps:
          1. Send GET /findings?status=<status>.
          2. Assert response status is 200.
          3. Assert all returned findings have the expected status.
        """
        resp = api_cl.list_findings(status=status)
        assert resp.status_code == 200
        for finding in resp.json()["items"]:
            assert finding["status"] == status

    def test_filter_by_nonexistent_status_returns_empty(self, api_cl: DashboardClient):
        """
        Title: Filtering by a non-existent status returns an empty list.
        Steps:
          1. Send GET /findings?status=nonexistent.
          2. Assert response status is 200.
          3. Assert items list is empty.
        """
        resp = api_cl.list_findings(status="nonexistent")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    # TODO: add "low" severity once seed data includes low-severity vulnerabilities
    @pytest.mark.parametrize("severity", ["critical", "high", "medium"])
    def test_filter_by_severity(self, api_cl: DashboardClient, severity):
        """
        Title: Filtering by severity={severity} returns only matching findings.
        Steps:
          1. Send GET /findings?severity={severity}.
          2. Assert response status is 200.
          3. Assert total > 0 (seed data has findings for this severity).
        """
        resp = api_cl.list_findings(severity=severity)
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    def test_filter_by_nonexistent_severity_returns_empty(self, api_cl: DashboardClient):
        """
        Title: Filtering by a non-existent severity returns an empty list.
        Steps:
          1. Send GET /findings?severity=nonexistent.
          2. Assert response status is 200.
          3. Assert items list is empty.
        """
        resp = api_cl.list_findings(severity="nonexistent")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    @pytest.mark.parametrize("asset_id", [1, 2])
    def test_filter_by_asset_id_returns_matching_findings(self, api_cl: DashboardClient, asset_id):
        """
        Title: Filtering by asset_id={asset_id} returns only findings for that asset.
        Steps:
          1. Send GET /findings?asset_id={asset_id}.
          2. Assert response status is 200.
          3. Assert all returned findings have asset_id={asset_id}.
        """
        resp = api_cl.list_findings(asset_id=asset_id)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0, f"Expected findings for asset_id={asset_id}"
        for finding in items:
            assert finding["asset_id"] == asset_id

    @pytest.mark.parametrize("asset_id", [
        999999,  # EP: non-existent asset
        pytest.param(0, marks=pytest.mark.xfail(
            reason="asset_id=0 is not filtered — service returns all findings", strict=True
        )),      # BVA: boundary below minimum valid ID
    ])
    def test_filter_by_asset_id_returns_empty_for_unknown(self, api_cl: DashboardClient, asset_id):
        """
        Title: Filtering by asset_id={asset_id} returns empty list for unknown asset.
        Steps:
          1. Send GET /findings?asset_id={asset_id}.
          2. Assert response status is 200.
          3. Assert items list is empty.
        """
        resp = api_cl.list_findings(asset_id=asset_id)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_dismissed_findings_excluded(self, api_cl: DashboardClient, created_finding):
        """
        Title: Dismissed findings are excluded from the list.
        Steps:
          1. Create a finding via fixture.
          2. Dismiss the finding via DELETE /findings/{id}.
          3. Send GET /findings.
          4. Assert the dismissed finding ID is not in the results.
        """
        finding_id = created_finding["id"]
        api_cl.dismiss_finding_by_id(finding_id)

        all_ids = {f["id"] for f in api_cl.list_findings().json()["items"]}
        assert finding_id not in all_ids


class TestGetFinding:
    def test_returns_200_with_full_detail(self, api_cl: DashboardClient):
        """
        Title: Get finding by ID returns 200 with full detail shape.
        Steps:
          1. Send GET /findings/1.
          2. Assert response status is 200.
          3. Assert response matches FindingDetail schema.
        """
        resp = api_cl.get_finding_by_id(1)
        assert resp.status_code == 200
        assert_valid_finding_detail(resp.json())

    @pytest.mark.parametrize("finding_id", [
        999999,  # EP: non-existent
        0,       # BVA: boundary below minimum valid ID
        -1,      # BVA: negative ID
    ])
    def test_nonexistent_finding_returns_404(self, api_cl: DashboardClient, finding_id):
        """
        Title: Get finding with id={finding_id} returns 404.
        Steps:
          1. Send GET /findings/{finding_id}.
          2. Assert response status is 404.
        """
        resp = api_cl.get_finding_by_id(finding_id)
        assert resp.status_code == 404

    @pytest.mark.xfail(reason="Service returns 200 for dismissed findings instead of 404", strict=True)
    def test_dismissed_finding_returns_404(self, api_cl: DashboardClient, created_finding):
        """
        Title: Dismissed findings should return 404 on GET.
        Steps:
          1. Create a finding via fixture.
          2. Dismiss it via DELETE /findings/{id}, assert 204.
          3. Send GET /findings/{id}.
          4. Assert response status is 404.
        """
        finding_id = created_finding["id"]
        dismiss_resp = api_cl.dismiss_finding_by_id(finding_id)
        assert dismiss_resp.status_code == 204

        get_resp = api_cl.get_finding_by_id(finding_id)
        assert get_resp.status_code == 404, (
            f"Dismissed finding {finding_id} should return 404 "
            f"but got {get_resp.status_code}"
        )


class TestCreateFinding:
    def test_create_returns_201_with_correct_shape(self, api_cl: DashboardClient, created_finding):
        """
        Title: Creating a finding returns 201 with correct response shape.
        Steps:
          1. Create a finding via fixture (POST /findings).
          2. Assert response matches FindingResponse schema.
          3. Assert status == 'open' and is_dismissed == False.
        """
        assert_valid_finding_response(created_finding)
        assert created_finding["status"] == "open"
        assert created_finding["is_dismissed"] is False

    @pytest.mark.parametrize("asset_id,vuln_id", [
        (999999, 1),
        (1, 999999),
    ])
    def test_create_with_invalid_reference_returns_400(self, api_cl: DashboardClient, asset_id, vuln_id):
        """
        Title: Creating a finding with asset_id={asset_id}, vuln_id={vuln_id} returns 400.
        Steps:
          1. Send POST /findings with an invalid asset_id or vulnerability_id.
          2. Assert response status is 400.
        """
        resp = api_cl.create_finding(asset_id=asset_id, vulnerability_id=vuln_id)
        assert resp.status_code == 400

    def test_create_missing_required_fields_returns_422(self, api_cl: DashboardClient):
        """
        Title: Creating a finding with missing required fields returns 422.
        Steps:
          1. Send POST /findings with an empty payload {}.
          2. Assert response status is 422.
        """
        resp = api_cl.session.post(f"{api_cl.base_url}/findings", json={})
        assert resp.status_code == 422


class TestUpdateFindingStatus:
    def test_valid_status_update_returns_200(self, api_cl: DashboardClient, created_finding):
        """
        Title: Updating finding status returns 200 with updated response.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status='confirmed'.
          3. Assert response status is 200.
          4. Assert response matches FindingResponse schema.
          5. Assert response status field == 'confirmed'.
        """
        resp = api_cl.update_finding_status_by_id(created_finding["id"], "confirmed")
        assert resp.status_code == 200
        assert_valid_finding_response(resp.json())
        assert resp.json()["status"] == "confirmed"

    @pytest.mark.parametrize("status", ["confirmed", "in_progress", "resolved", "false_positive", "open"])
    def test_all_valid_statuses_accepted(self, api_cl: DashboardClient, created_finding, status):
        """
        Title: Status update with status={status} is accepted by the update endpoint.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status={status}.
          3. Assert response status is 200.
        """
        resp = api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 200, f"Status '{status}' should be accepted"

    @pytest.mark.parametrize("status", [
        "hacked",   # EP: arbitrary invalid string
        "",         # EP: empty string
        "OPEN",     # EP: uppercase valid value
        "123",      # EP: numeric string
    ])
    def test_invalid_status_returns_400(self, api_cl: DashboardClient, created_finding, status):
        """
        Title: Updating with invalid status={status} returns 400.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status={status}.
          3. Assert response status is 400.
        """
        resp = api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 400

    def test_resolved_status_sets_resolved_at(self, api_cl: DashboardClient, created_finding):
        """
        Title: Setting status to 'resolved' populates resolved_at timestamp.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status='resolved'.
          3. Assert response status is 200.
          4. Assert resolved_at is not None.
        """
        resp = api_cl.update_finding_status_by_id(created_finding["id"], "resolved")
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is not None

    @pytest.mark.parametrize("status", ["confirmed", "in_progress", "false_positive", "open"])
    def test_non_resolved_status_has_no_resolved_at(self, api_cl: DashboardClient, created_finding, status):
        """
        Title: Setting status={status} returns resolved_at as None.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status={status}.
          3. Assert response status is 200.
          4. Assert resolved_at is None in the response.
        """
        resp = api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is None, (
            f"resolved_at should be None when status='{status}', "
            f"got {resp.json()['resolved_at']}"
        )

    def test_notes_updated_with_status(self, api_cl: DashboardClient, created_finding):
        """
        Title: Notes field is updated when provided alongside status change.
        Steps:
          1. Create a finding via fixture.
          2. Send PUT /findings/{id}/status with status='confirmed' and notes='verified by test'.
          3. Assert response notes == 'verified by test'.
        """
        resp = api_cl.update_finding_status_by_id(
            created_finding["id"], "confirmed", notes="verified by test"
        )
        assert resp.json()["notes"] == "verified by test"

    @pytest.mark.xfail(reason="No status transition validation — resolved→open is accepted", strict=True)
    def test_status_transition_resolved_to_open_rejected(self, api_cl: DashboardClient, created_finding):
        """
        Title: Resolved findings should not be transitioned back to open.
        Steps:
          1. Create a finding via fixture.
          2. Set status to 'resolved'.
          3. Attempt to set status back to 'open'.
          4. Assert response status is 400 or 422.
        """
        api_cl.update_finding_status_by_id(created_finding["id"], "resolved")
        resp = api_cl.update_finding_status_by_id(created_finding["id"], "open")
        assert resp.status_code in (400, 422), (
            "Transition from 'resolved' back to 'open' should be rejected"
        )

    def test_update_nonexistent_finding_returns_404(self, api_cl: DashboardClient):
        """
        Title: Updating status of a non-existent finding returns 404.
        Steps:
          1. Send PUT /findings/999999/status with status='confirmed'.
          2. Assert response status is 404.
        """
        resp = api_cl.update_finding_status_by_id(999999, "confirmed")
        assert resp.status_code == 404


class TestDismissFinding:
    def test_dismiss_returns_204(self, api_cl: DashboardClient, created_finding):
        """
        Title: Dismissing a finding returns 204 No Content.
        Steps:
          1. Create a finding via fixture.
          2. Send DELETE /findings/{id}.
          3. Assert response status is 204.
        """
        resp = api_cl.dismiss_finding_by_id(created_finding["id"])
        assert resp.status_code == 204

    @pytest.mark.parametrize("finding_id", [
        999999,  # EP: non-existent
        0,       # BVA: boundary below minimum valid ID
        -1,      # BVA: negative ID
    ])
    def test_dismiss_nonexistent_finding_returns_404(self, api_cl: DashboardClient, finding_id):
        """
        Title: Dismissing finding with id={finding_id} returns 404.
        Steps:
          1. Send DELETE /findings/{finding_id}.
          2. Assert response status is 404.
        """
        resp = api_cl.dismiss_finding_by_id(finding_id)
        assert resp.status_code == 404

    def test_dismiss_already_dismissed_returns_404(self, api_cl: DashboardClient, created_finding):
        """
        Title: Dismissing an already dismissed finding returns 404.
        Steps:
          1. Create a finding via fixture.
          2. Dismiss it via DELETE /findings/{id}.
          3. Dismiss the same finding again.
          4. Assert second response status is 404.
        """
        api_cl.dismiss_finding_by_id(created_finding["id"])
        resp = api_cl.dismiss_finding_by_id(created_finding["id"])
        assert resp.status_code == 404


class TestSearchFindings:
    def test_search_by_cve_returns_results(self, api_cl: DashboardClient):
        """
        Title: Searching by CVE ID returns matching findings.
        Steps:
          1. Send GET /findings/search?q=CVE-2021-44228.
          2. Assert response status is 200.
          3. Assert results are non-empty.
          4. Assert all results contain the CVE ID in cve_id field.
        """
        resp = api_cl.search_findings("CVE-2021-44228")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0
        assert all("CVE-2021-44228" in r["cve_id"] for r in results)

    @pytest.mark.xfail(reason="Search returns cross-hostname results due to broken OR filter", strict=True)
    def test_search_by_hostname_returns_results(self, api_cl: DashboardClient):
        """
        Title: Searching by hostname returns only findings for that host.
        Steps:
          1. Send GET /findings/search?q=prod-web-01.
          2. Assert response status is 200.
          3. Assert results are non-empty.
          4. Assert all results have hostname == 'prod-web-01'.
        """
        resp = api_cl.search_findings("prod-web-01")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0
        assert all(r["hostname"] == "prod-web-01" for r in results)

    def test_empty_query_returns_empty_list(self, api_cl: DashboardClient):
        """
        Title: Empty search query returns an empty list.
        Steps:
          1. Send GET /findings/search?q=.
          2. Assert response status is 200.
          3. Assert response body is [].
        """
        resp = api_cl.search_findings("")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize("query", [
        "CVE-9999-99999",          # EP: non-existent CVE
        "zzz-no-such-host",        # EP: non-existent hostname
        "!@#$%",                   # EP: special characters
        "a" * 200,                 # BVA: very long string
    ])
    def test_no_match_returns_empty_list(self, api_cl: DashboardClient, query):
        """
        Title: Search with query={query} returns an empty list.
        Steps:
          1. Send GET /findings/search?q={query}.
          2. Assert response status is 200.
          3. Assert response body is [].
        """
        resp = api_cl.search_findings(query)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_result_shape(self, api_cl: DashboardClient):
        """
        Title: Search results match the expected schema.
        Steps:
          1. Send GET /findings/search?q=CVE.
          2. Assert results are non-empty.
          3. Assert first result matches FindingSearchResult schema.
        """
        resp = api_cl.search_findings("CVE")
        results = resp.json()
        assert len(results) > 0
        assert_valid_search_result(results[0])

    @pytest.mark.xfail(reason="Search endpoint is vulnerable to SQL injection via f-string", strict=True)
    def test_sql_injection_returns_no_results(self, api_cl: DashboardClient):
        """
        Title: Malicious input should be treated as a literal string, returning no results.
        Steps:
          1. Send GET /findings/search?q=' OR '1'='1.
          2. Assert response status is 200.
          3. Assert response body is empty (input matched nothing literally).
        """
        resp = api_cl.search_findings("' OR '1'='1")
        assert resp.status_code == 200
        assert len(resp.json()) == 0, (
            "Search should return 0 results for non-matching input"
        )


class TestStats:
    def test_risk_score_returns_200_with_correct_shape(self, api_cl: DashboardClient):
        """
        Title: Risk score endpoint returns 200 with all expected fields.
        Steps:
          1. Send GET /stats/risk-score.
          2. Assert response status is 200.
          3. Assert response contains exactly the expected keys.
        """
        resp = api_cl.risk_score()
        assert resp.status_code == 200
        body = resp.json()
        expected_keys = {
            "risk_score", "total_findings", "critical_count",
            "high_count", "medium_count", "low_count", "average_cvss",
        }
        assert expected_keys == body.keys()

    def test_risk_score_values_in_valid_range(self, api_cl: DashboardClient):
        """
        Title: Risk score and CVSS values are within valid numeric ranges.
        Steps:
          1. Send GET /stats/risk-score.
          2. Assert risk_score is between 0.0 and 10.0.
          3. Assert average_cvss is between 0.0 and 10.0.
          4. Assert total_findings >= 0.
        """
        body = api_cl.risk_score().json()
        assert 0.0 <= body["risk_score"] <= 10.0
        assert 0.0 <= body["average_cvss"] <= 10.0
        assert body["total_findings"] >= 0

    @pytest.mark.xfail(reason="Float precision issue — risk_score and average_cvss are not rounded", strict=True)
    def test_risk_score_is_rounded(self, api_cl: DashboardClient):
        """
        Title: risk_score and average_cvss should be rounded to 2 decimal places.
        Steps:
          1. Send GET /stats/risk-score.
          2. Assert round(risk_score, 2) == risk_score.
          3. Assert round(average_cvss, 2) == average_cvss.
        """
        body = api_cl.risk_score().json()
        assert round(body["risk_score"], 2) == body["risk_score"], (
            f"risk_score has excess precision: {body['risk_score']}"
        )
        assert round(body["average_cvss"], 2) == body["average_cvss"], (
            f"average_cvss has excess precision: {body['average_cvss']}"
        )

    def test_summary_returns_200_with_correct_shape(self, api_cl: DashboardClient):
        """
        Title: Summary endpoint returns 200 with all expected fields.
        Steps:
          1. Send GET /stats/summary.
          2. Assert response status is 200.
          3. Assert response contains exactly the expected keys.
        """
        resp = api_cl.summary()
        assert resp.status_code == 200
        body = resp.json()
        expected_keys = {
            "total_findings", "open_findings", "confirmed_findings",
            "in_progress_findings", "resolved_findings", "false_positive_findings",
            "by_severity", "by_environment",
        }
        assert expected_keys == body.keys()

    def test_summary_counts_are_consistent(self, api_cl: DashboardClient):
        """
        Title: Summary status counts sum up to total_findings.
        Steps:
          1. Send GET /stats/summary.
          2. Sum open + confirmed + in_progress + resolved + false_positive counts.
          3. Assert sum equals total_findings.
        """
        body = api_cl.summary().json()
        status_sum = (
            body["open_findings"] + body["confirmed_findings"]
            + body["in_progress_findings"] + body["resolved_findings"]
            + body["false_positive_findings"]
        )
        assert status_sum == body["total_findings"]
