import uuid
import pytest
from clients.dashboard_client import DashboardClient
from services.finding_actions import FindingActions
from validators.finding_schema import (
    assert_finding_response_schema,
    assert_finding_detail_schema,
    assert_search_result_schema,
    assert_paginated_findings_schema,
    assert_error_response_schema,
    assert_422_response_schema,
)


class TestHealthCheck:
    def test_health_returns_200(self, dashboard_api_cl: DashboardClient):
        """Title: Health check endpoint returns 200.

        Steps:
        1. Send GET /health.
        2. Assert response status is 200.
        """
        resp = dashboard_api_cl.health()
        assert resp.status_code == 200
        resp_json = resp.json()
        assert len(resp_json) == 2, f"Expected exactly 2 fields in health response, got {len(resp_json)}"
        assert resp_json["status"] == "healthy"
        assert resp_json["service"] == "dashboard-api"


class TestListFindings:

    # --- Positive: pagination ---

    def test_returns_200_with_expected_pagination(self, dashboard_api_cl: DashboardClient):
        """Title: GET /findings returns 200 with valid paginated shape.

        Steps:
        1. Send GET /findings.
        2. Assert response status is 200.
        3. Assert response body matches paginated findings schema.
        """
        resp = dashboard_api_cl.list_findings()
        assert resp.status_code == 200
        assert_paginated_findings_schema(resp.json())

    def test_default_pagination(self, dashboard_api_cl: DashboardClient):
        """Title: GET /findings uses page=1 and per_page=20 by default.

        Steps:
        1. Send GET /findings without pagination params.
        2. Assert page == 1 and per_page == 20.
        3. Assert response matches paginated findings schema.
        """
        resp = dashboard_api_cl.list_findings()
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["per_page"] == 20
        assert_paginated_findings_schema(body)

    @pytest.mark.parametrize("per_page", [1, 10, 100])
    def test_valid_per_page_param(self, dashboard_api_cl: DashboardClient, per_page):
        """Title: GET /findings with valid per_page={per_page} returns 200 with correct pagination.

        Steps:
        1. Send GET /findings?per_page={per_page}.
        2. Assert response status is 200.
        3. Assert per_page in response matches the requested value.
        4. Assert response matches paginated findings schema.
        """
        resp = dashboard_api_cl.list_findings(per_page=per_page)
        assert resp.status_code == 200
        body = resp.json()
        assert body["per_page"] == per_page
        assert_paginated_findings_schema(body)

    @pytest.mark.parametrize("page", [1, 5, 10])
    def test_valid_page_param(self, dashboard_api_cl: DashboardClient, page):
        """Title: GET /findings with valid page={page} returns 200 with correct page number.

        Steps:
        1. Send GET /findings?page={page}.
        2. Assert response status is 200.
        3. Assert page in response matches the requested value.
        4. Assert response matches paginated findings schema.
        """
        resp = dashboard_api_cl.list_findings(page=page)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == page
        assert_paginated_findings_schema(body)

    def test_page_beyond_data_returns_empty(self, dashboard_api_cl: DashboardClient):
        """Title: GET /findings with page far beyond total returns 200 with empty items.

        Steps:
        1. Send GET /findings?page=999999.
        2. Assert response status is 200.
        3. Assert items list is empty.
        4. Assert page in response matches the requested value.
        """
        resp = dashboard_api_cl.list_findings(page=999999)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["page"] == 999999
        assert_paginated_findings_schema(body)

    def test_pagination_returns_different_pages(self, dashboard_api_cl: DashboardClient):
        """Title: Paginated results do not overlap between pages.

        Steps:
        1. Send GET /findings?page=1&per_page=2.
        2. Send GET /findings?page=2&per_page=2.
        3. Assert finding IDs from page 1 and page 2 not overlapped.
        4. Assert both pages match paginated findings schema.
        """
        page1 = dashboard_api_cl.list_findings(page=1, per_page=1).json()
        page2 = dashboard_api_cl.list_findings(page=2, per_page=1).json()
        assert page1["page"] == 1
        assert page2["page"] == 2
        ids_p1 = {f["id"] for f in page1["items"]}
        ids_p2 = {f["id"] for f in page2["items"]}
        assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"
        for page in [page1, page2]:
            assert_paginated_findings_schema(page)

    # --- Negative: params ---

    @pytest.mark.parametrize("param,value,expected_type,expected_msg", [
        ("per_page", 0,   "greater_than_equal", "Input should be greater than or equal to 1"),
        ("per_page", -1,  "greater_than_equal", "Input should be greater than or equal to 1"),
        ("per_page", 101, "less_than_equal",    "Input should be less than or equal to 100"),
        ("page",     0,   "greater_than_equal", "Input should be greater than or equal to 1"),
        ("page",     -1,  "greater_than_equal", "Input should be greater than or equal to 1"),
    ])
    def test_integer_param_out_of_range_returns_422(
        self, dashboard_api_cl: DashboardClient, param, value, expected_type, expected_msg
    ):
        """Title: GET /findings with out-of-range {param}={value} returns 422.

        Steps:
        1. Send GET /findings?{param}={value}.
        2. Assert response status is 422.
        3. Assert error body structure matches FastAPI validation error schema.
        4. Assert error points to the correct query parameter.
        5. Assert error type and message match expected values.
        """
        resp = dashboard_api_cl.list_findings(**{param: value})
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())

        error = resp.json()["detail"][0]
        assert error["loc"] == ["query", param], (
            f"Expected error on ['query', '{param}'], got: {error['loc']}"
        )
        assert error["type"] == expected_type, (
            f"Expected type '{expected_type}', got: {error['type']}"
        )
        assert error["msg"] == expected_msg, (
            f"Expected msg '{expected_msg}', got: {error['msg']}"
        )

    @pytest.mark.parametrize("param", ["page", "per_page", "asset_id"])
    @pytest.mark.parametrize("value", ["abc", "1.5", "!@#", " "])
    def test_integer_param_wrong_type_returns_422(
        self, dashboard_api_cl: DashboardClient, param, value
    ):
        """Title: GET /findings with non-integer {param}={value!r} returns 422.

        Steps:
        1. Send GET /findings?{param}={value!r}.
        2. Assert response status is 422.
        3. Assert error body structure matches FastAPI validation error schema.
        4. Assert error points to the correct query parameter.
        5. Assert error type is 'int_parsing' and message indicates integer parse failure.
        """
        resp = dashboard_api_cl.list_findings(**{param: value})
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())

        error = resp.json()["detail"][0]
        assert error["loc"] == ["query", param], (
            f"Expected error on ['query', '{param}'], got: {error['loc']}"
        )
        assert error["type"] == "int_parsing", (
            f"Expected type 'int_parsing', got: {error['type']}"
        )
        assert error["msg"] == "Input should be a valid integer, unable to parse string as an integer", (
            f"Unexpected error message: {error['msg']}"
        )

    def test_unknown_query_param_is_ignored(self, dashboard_api_cl: DashboardClient):
        """Title: GET /findings with unknown query parameter returns 200 and ignores the param.

        Steps:
        1. Send GET /findings?unknown_param=foo.
        2. Assert response status is 200.
        3. Assert response body matches paginated findings schema.
        """
        resp = dashboard_api_cl.list_findings(unknown_param="foo")
        assert resp.status_code == 200
        assert_paginated_findings_schema(resp.json())

    # --- Positive: filters ---

    @pytest.mark.parametrize("status", ["open", "confirmed", "in_progress", "resolved", "false_positive"])
    def test_filter_by_status(self, dashboard_api_cl: DashboardClient, status):
        """Title: Filtering by status={status} returns only matching findings.

        Steps:
        1. Send GET /findings?status={status}.
        2. Assert response status is 200.
        3. [Precondition] Assert at least one finding with status={status} exists.
        4. Assert all returned findings match FindingResponse schema.
        5. Assert all returned findings have the expected status and are not dismissed.
        """
        resp = dashboard_api_cl.list_findings(status=status)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0, f"Precondition failed: no findings with status='{status}' found"
        assert_paginated_findings_schema(resp.json())
        for finding in items:
            assert finding["status"] == status
            assert finding["is_dismissed"] is False

    # TODO: add "low" severity once seed data includes low-severity vulnerabilities
    # TODO: Could be implemented by forced SQL INSERT (to clarify)
    @pytest.mark.parametrize("severity", ["critical", "high", "medium"])
    def test_filter_by_severity(self, dashboard_api_cl: DashboardClient, severity):
        """Title: Filtering by severity={severity} returns only matching findings.

        Steps:
        1. Send GET /findings?severity={severity}.
        2. Assert response status is 200.
        3. [Precondition] Assert at least one finding with severity={severity} exists.
        4. Assert response matches paginated findings schema.
        Note: severity cross-field check not possible — list response does not include severity per item.
        """
        resp = dashboard_api_cl.list_findings(severity=severity)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) > 0, f"Precondition failed: no findings with severity='{severity}' found"
        assert_paginated_findings_schema(body)

    def test_filter_by_asset_id_returns_matching_findings(
        self, dashboard_api_cl: DashboardClient, created_finding, valid_asset
    ):
        """Title: Filtering by asset_id returns only findings for that asset.

        Steps:
        1. Send POST /findings to ensure at least one finding exists for the test asset.
        2. Send GET /findings?asset_id={valid_asset["id"]}.
        3. Assert response status is 200.
        4. Assert all returned findings match FindingResponse schema.
        5. Assert all returned findings have the expected asset_id.
        """
        asset_id = valid_asset["id"]
        resp = dashboard_api_cl.list_findings(asset_id=asset_id)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0, f"Expected findings for asset_id={asset_id}"
        for finding in items:
            assert_finding_response_schema(finding)
            assert finding["asset_id"] == asset_id

    # --- Negative: filters ---

    @pytest.mark.parametrize("param", ["status", "severity"])
    @pytest.mark.parametrize("value", ["nonexistent", "OPEN", "123", "!@#", "criti", "conf"])
    def test_string_filter_param_invalid_enum_returns_empty(
        self, dashboard_api_cl: DashboardClient, param, value
    ):
        """Title: GET /findings with invalid enum {param}={value!r} returns 200 with empty list.

        Steps:
        1. Send GET /findings?{param}={value!r}.
        2. Assert response status is 200.
        3. Assert items list is empty.
        """
        resp = dashboard_api_cl.list_findings(**{param: value})
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert_paginated_findings_schema(resp.json())

    @pytest.mark.parametrize("param", ["status", "severity"])
    def test_empty_string_filter_is_ignored(self, dashboard_api_cl: DashboardClient, param):
        """Title: GET /findings with empty string {param}='' ignores the filter and returns all findings.

        Steps:
        1. Send GET /findings?{param}=''.
        2. Assert response status is 200.
        3. Assert items list is not empty (filter was ignored, not applied).
        """
        resp = dashboard_api_cl.list_findings(**{param: ""})
        assert resp.status_code == 200
        assert len(resp.json()["items"]) > 0

    @pytest.mark.parametrize("asset_id", [
        999999,
        -1,
        pytest.param(0, marks=pytest.mark.xfail(
            reason="asset_id=0 is not filtered — service returns all findings", strict=True
        )),
    ])
    def test_filter_by_asset_id_returns_empty_for_unknown(self, dashboard_api_cl: DashboardClient, asset_id):
        """Title: Filtering by unknown asset_id={asset_id} returns an empty list.

        Steps:
        1. Send GET /findings?asset_id={asset_id}.
        2. Assert response status is 200.
        3. Assert items list is empty.
        """
        resp = dashboard_api_cl.list_findings(asset_id=asset_id)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert_paginated_findings_schema(resp.json())

    def test_dismissed_findings_excluded(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Dismissed findings are excluded from the list.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Dismiss the finding via DELETE /findings/{id}.
        3. Send GET /findings.
        4. Assert the dismissed finding ID is not in the results.
        """
        finding_id = created_finding["id"]
        dashboard_api_cl.dismiss_finding_by_id(finding_id)

        resp = dashboard_api_cl.list_findings(asset_id=created_finding["asset_id"], per_page=100)
        assert resp.status_code == 200
        all_ids = {f["id"] for f in resp.json()["items"]}
        assert finding_id not in all_ids
        assert_paginated_findings_schema(resp.json())


class TestGetFinding:
    def test_returns_200_with_full_detail(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Get finding by ID returns 200 with full detail shape.

        Steps:
        1. Create a finding.
        2. Send GET /findings/{id}.
        3. Assert response status is 200.
        4. Assert response matches FindingDetail schema.
        """
        resp = dashboard_api_cl.get_finding_by_id(created_finding["id"])
        assert resp.status_code == 200
        assert_finding_detail_schema(resp.json())

    @pytest.mark.parametrize("finding_id", [999999, 0, -1])
    def test_nonexistent_finding_returns_404(self, dashboard_api_cl: DashboardClient, finding_id):
        """Title: Get finding with id={finding_id} returns 404.

        Steps:
        1. Send GET /findings/{finding_id}.
        2. Assert response status is 404.
        3. Assert error response body contains 'detail' field.
        """
        resp = dashboard_api_cl.get_finding_by_id(finding_id)
        assert resp.status_code == 404
        assert_error_response_schema(resp.json(), expected_fragment="not found")

    @pytest.mark.xfail(reason="Service returns 200 for dismissed findings instead of 404", strict=True)
    def test_dismissed_finding_returns_404(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Dismissed finding should return 404 on GET.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Dismiss it via DELETE /findings/{id}, assert 204.
        3. Send GET /findings/{id}.
        4. Assert response status is 404.
        """
        finding_id = created_finding["id"]
        dismiss_resp = dashboard_api_cl.dismiss_finding_by_id(finding_id)
        assert dismiss_resp.status_code == 204
        get_resp = dashboard_api_cl.get_finding_by_id(finding_id)
        assert get_resp.status_code == 404, (
            f"Dismissed finding {finding_id} should return 404 "
            f"but got {get_resp.status_code}"
        )
        assert_error_response_schema(get_resp.json(), expected_fragment="not found")

    def test_resolved_at_is_none_for_non_resolved_finding(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: resolved_at is None in FindingDetail when status is not 'resolved'.

        Steps:
        1. Send POST /findings to create a new finding (status defaults to 'open').
        2. Send GET /findings/{id}.
        3. Assert response status is 200.
        4. Assert resolved_at is None.
        """
        resp = dashboard_api_cl.get_finding_by_id(created_finding["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_detail_schema(body)
        assert body["resolved_at"] is None

    def test_resolved_at_set_for_resolved_finding(
        self, finding_actions: FindingActions, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: resolved_at is a non-null string in FindingDetail when status is 'resolved'.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Update status to 'resolved'.
        3. Send GET /findings/{id}.
        4. Assert response status is 200.
        5. Assert resolved_at is a non-null string (ISO 8601).
        """
        finding_actions.update_status(created_finding["id"], "resolved")
        resp = dashboard_api_cl.get_finding_by_id(created_finding["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_detail_schema(body)
        assert body["resolved_at"] is not None
        assert isinstance(body["resolved_at"], str)

    def test_notes_returned_when_set(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: notes field is returned correctly in FindingDetail when set at creation.

        Steps:
        1. Send POST /findings with notes='created by test fixture'.
        2. Send GET /findings/{id}.
        3. Assert response status is 200.
        4. Assert notes == 'created by test fixture'.
        """
        resp = dashboard_api_cl.get_finding_by_id(created_finding["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_detail_schema(body)
        assert body["notes"] == "created by test fixture"

    def test_notes_is_none_when_not_set(
        self, finding_actions: FindingActions, dashboard_api_cl: DashboardClient,
        valid_asset, valid_vulnerability
    ):
        """Title: notes field is None in FindingDetail when not provided at creation.

        Steps:
        1. Create a finding without notes.
        2. Send GET /findings/{id}.
        3. Assert response status is 200.
        4. Assert notes is None.
        5. Dismiss the finding for cleanup.
        """
        finding = finding_actions.create(
            asset_id=valid_asset["id"],
            vulnerability_id=valid_vulnerability["id"],
            notes=None,
        )
        try:
            resp = dashboard_api_cl.get_finding_by_id(finding["id"])
            assert resp.status_code == 200
            body = resp.json()
            assert_finding_detail_schema(body)
            assert body["notes"] is None
        finally:
            finding_actions.dismiss(finding["id"])

    def test_vulnerability_object_structure(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: Nested vulnerability object in FindingDetail has correct fields and types.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send GET /findings/{id}.
        3. Assert response status is 200.
        4. Assert vulnerability object matches VulnerabilityResponse schema.
        """
        resp = dashboard_api_cl.get_finding_by_id(created_finding["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_detail_schema(body)
        assert body["vulnerability"] is not None, "vulnerability field should not be None for a valid finding"

    def test_string_id_in_path_returns_422(self, dashboard_api_cl: DashboardClient):
        """Title: GET /findings/{id} with a non-integer ID returns 422.

        Steps:
        1. Send GET /findings/abc.
        2. Assert response status is 422.
        3. Assert error body matches FastAPI 422 validation error schema.
        4. Assert error points to path param 'finding_id' with type 'int_parsing'.
        """
        resp = dashboard_api_cl.get_finding_by_id("abc")
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        error = resp.json()["detail"][0]
        assert error["loc"] == ["path", "finding_id"], f"Unexpected loc: {error['loc']}"
        assert error["type"] == "int_parsing", f"Unexpected type: {error['type']}"
        assert error["msg"] == "Input should be a valid integer, unable to parse string as an integer", (
            f"Unexpected msg: {error['msg']}"
        )


class TestCreateFinding:
    def test_create_returns_201_with_correct_shape(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability
    ):
        """Title: Creating a finding returns 201 with correct response shape.

        Steps:
        1. Send POST /findings with valid asset_id and vulnerability_id.
        2. Assert response status is 201.
        3. Assert response matches FindingResponse schema.
        4. Assert status == 'open' and is_dismissed == False.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            "scanner": "pytest",
        })
        try:
            assert resp.status_code == 201
            body = resp.json()
            assert_finding_response_schema(body)
            assert body["status"] == "open"
            assert body["is_dismissed"] is False
            assert body["asset_id"] == valid_asset["id"]
            assert body["vulnerability_id"] == valid_vulnerability["id"]
        finally:
            finding_actions.dismiss(body["id"])

    @pytest.mark.parametrize("payload,expected_missing", [
        ({},                       "asset_id"),
        ({"vulnerability_id": 1},  "asset_id"),
        ({"asset_id": 1},          "vulnerability_id"),
    ])
    def test_create_missing_required_field_returns_422(
        self, dashboard_api_cl: DashboardClient, payload, expected_missing
    ):
        """Title: Creating a finding with missing required field returns 422.

        Steps:
        1. Send POST /findings with payload missing {expected_missing}.
        2. Assert response status is 422.
        3. Assert error body matches 422 schema.
        4. Assert error references the missing field in body with type 'missing'.
        """
        resp = dashboard_api_cl.create_finding(payload)
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        errors = {tuple(e["loc"]): e for e in resp.json()["detail"]}
        field_error = errors.get(("body", expected_missing))
        assert field_error is not None, f"Expected error on ['body', '{expected_missing}'], got locs: {list(errors.keys())}"
        assert field_error["type"] == "missing", f"Unexpected type: {field_error['type']}"
        assert field_error["msg"] == "Field required", f"Unexpected msg: {field_error['msg']}"

    @pytest.mark.parametrize("field,value,expected_type,expected_msg", [
        ("asset_id",        "abc", "int_parsing", "Input should be a valid integer, unable to parse string as an integer"),
        ("asset_id",        None,  "int_type",    "Input should be a valid integer"),
        ("vulnerability_id","abc", "int_parsing", "Input should be a valid integer, unable to parse string as an integer"),
        ("vulnerability_id", None, "int_type",    "Input should be a valid integer"),
    ])
    def test_create_required_field_wrong_type_returns_422(
        self, dashboard_api_cl: DashboardClient, valid_asset, valid_vulnerability,
        field, value, expected_type, expected_msg
    ):
        """Title: Creating a finding with wrong type for {field}={value!r} returns 422.

        Steps:
        1. Send POST /findings with {field}={value!r} overriding the valid value.
        2. Assert response status is 422.
        3. Assert error body matches 422 schema.
        4. Assert error references the correct body field with expected type and message.
        """
        payload = {
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
        }
        payload[field] = value
        resp = dashboard_api_cl.create_finding(payload)
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        errors = {tuple(e["loc"]): e for e in resp.json()["detail"]}
        field_error = errors.get(("body", field))
        assert field_error is not None, f"Expected error on ['body', '{field}'], got locs: {list(errors.keys())}"
        assert field_error["type"] == expected_type, f"Unexpected type: {field_error['type']}"
        assert field_error["msg"] == expected_msg, f"Unexpected msg: {field_error['msg']}"

    @pytest.mark.parametrize("asset_id,vuln_id,expected_fragment", [
        (999999, 1,      "Asset not found"),
        (0,      1,      "Asset not found"),
        (-1,     1,      "Asset not found"),
        (1,      999999, "Vulnerability not found"),
        (1,      0,      "Vulnerability not found"),
        (1,      -1,     "Vulnerability not found"),
    ])
    def test_create_with_invalid_reference_returns_400(
        self, dashboard_api_cl: DashboardClient, asset_id, vuln_id, expected_fragment
    ):
        """Title: Creating a finding with a non-existent asset or vulnerability returns 400.

        Steps:
        1. Send POST /findings with asset_id={asset_id} and vulnerability_id={vuln_id}.
        2. Assert response status is 400.
        3. Assert error detail contains the specific 'not found' message for the invalid resource.
        """
        resp = dashboard_api_cl.create_finding({"asset_id": asset_id, "vulnerability_id": vuln_id})
        assert resp.status_code == 400
        assert_error_response_schema(resp.json(), expected_fragment=expected_fragment)

    @pytest.mark.parametrize("field,value", [
        ("scanner", "nessus"),
        ("notes", "test note"),
    ])
    def test_create_optional_field_returned_in_response(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability, field, value
    ):
        """Title: Optional field {field}={value!r} set at creation is returned in response.

        Steps:
        1. Send POST /findings with {field}={value!r}.
        2. Assert response status is 201.
        3. Assert response matches FindingResponse schema.
        4. Assert {field} in response equals {value!r}.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            field: value,
        })
        assert resp.status_code == 201
        body = resp.json()
        try:
            assert_finding_response_schema(body)
            assert body[field] == value
        finally:
            finding_actions.dismiss(body["id"])

    def test_create_optional_fields_absent_returns_null(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability
    ):
        """Title: Omitting optional fields scanner and notes results in null values in response.

        Steps:
        1. Send POST /findings with only required fields (no scanner, no notes).
        2. Assert response status is 201.
        3. Assert response matches FindingResponse schema.
        4. Assert scanner is None and notes is None.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
        })
        assert resp.status_code == 201
        body = resp.json()
        try:
            assert_finding_response_schema(body)
            assert body["scanner"] is None
            assert body["notes"] is None
        finally:
            finding_actions.dismiss(body["id"])

    def test_create_unknown_field_in_payload_is_ignored(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability
    ):
        """Title: Unknown extra fields in POST /findings payload are ignored.

        Steps:
        1. Send POST /findings with an extra unknown field.
        2. Assert response status is 201.
        3. Assert response matches FindingResponse schema.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            "unknown_field": "ignored",
        })
        assert resp.status_code == 201
        body = resp.json()
        try:
            assert_finding_response_schema(body)
        finally:
            finding_actions.dismiss(body["id"])

    def test_create_duplicate_finding_is_allowed(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability
    ):
        """Title: Creating the same finding twice results in two separate findings with unique IDs.

        Steps:
        1. Send POST /findings twice with identical payload.
        2. Assert both responses have status 201.
        3. Assert both responses match FindingResponse schema.
        4. Assert the two returned IDs are different.
        """
        payload = {
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            "scanner": "pytest",
        }
        resp1 = dashboard_api_cl.create_finding(payload)
        resp2 = dashboard_api_cl.create_finding(payload)
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        body1, body2 = resp1.json(), resp2.json()
        try:
            assert_finding_response_schema(body1)
            assert_finding_response_schema(body2)
            assert body1["id"] != body2["id"], "Duplicate findings must have different IDs"
        finally:
            finding_actions.dismiss(body1["id"])
            finding_actions.dismiss(body2["id"])

    @pytest.mark.parametrize("field,value", [
        ("scanner", ""),
        ("scanner", "a" * 100),
        ("notes", ""),
        ("notes", "z" * 10000),
    ])
    def test_create_string_field_boundary_values_accepted(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability, field, value
    ):
        """Title: String field {field} with boundary value is accepted and returned correctly.

        Steps:
        1. Send POST /findings with {field} set to a boundary value.
        2. Assert response status is 201.
        3. Assert response matches FindingResponse schema.
        4. Assert {field} in response equals the sent value.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            field: value,
        })
        assert resp.status_code == 201
        body = resp.json()
        try:
            assert_finding_response_schema(body)
            assert body[field] == value
        finally:
            finding_actions.dismiss(body["id"])

    @pytest.mark.xfail(
        reason="scanner has no Pydantic length validation — String(100) DB limit may cause 500",
        strict=True,
    )
    def test_create_scanner_over_max_length_returns_422(
        self, dashboard_api_cl: DashboardClient, valid_asset, valid_vulnerability
    ):
        """Title: scanner value exceeding DB limit (>100 chars) should return 422.

        Steps:
        1. Send POST /findings with scanner='a'*101.
        2. Assert response status is 422.
        3. Assert error body matches 422 schema.
        """
        resp = dashboard_api_cl.create_finding({
            "asset_id": valid_asset["id"],
            "vulnerability_id": valid_vulnerability["id"],
            "scanner": "a" * 101,
        })
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())


class TestUpdateFindingStatus:
    def test_valid_status_update_returns_200(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Updating finding status returns 200 with updated response.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='confirmed'.
        3. Assert response status is 200.
        4. Assert response matches FindingResponse schema.
        5. Assert response status field == 'confirmed'.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], "confirmed")
        assert resp.status_code == 200
        assert_finding_response_schema(resp.json())
        assert resp.json()["status"] == "confirmed"

    @pytest.mark.parametrize("status", ["confirmed", "in_progress", "resolved", "false_positive", "open"])
    def test_all_valid_statuses_accepted(self, dashboard_api_cl: DashboardClient, created_finding, status):
        """Title: Status update with status={status} is accepted and reflected in response.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status={status}.
        3. Assert response status is 200.
        4. Assert response matches FindingResponse schema with correct status field.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 200, f"Status '{status}' should be accepted"
        body = resp.json()
        assert_finding_response_schema(body)
        assert body["status"] == status

    @pytest.mark.parametrize("status", ["hacked", "", "OPEN", "123"])
    def test_invalid_status_returns_400(self, dashboard_api_cl: DashboardClient, created_finding, status):
        """Title: Updating with invalid status={status} returns 400.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status={status}.
        3. Assert response status is 400.
        4. Assert error response body contains 'detail' field.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 400
        assert_error_response_schema(resp.json(), expected_fragment="invalid status")

    def test_resolved_status_sets_resolved_at(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Setting status to 'resolved' populates the resolved_at timestamp.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='resolved'.
        3. Assert response status is 200.
        4. Assert resolved_at is not None.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], "resolved")
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_response_schema(body)
        assert body["resolved_at"] is not None

    @pytest.mark.parametrize("status", ["confirmed", "in_progress", "false_positive", "open"])
    def test_non_resolved_status_has_no_resolved_at(self, dashboard_api_cl: DashboardClient, created_finding, status):
        """Title: Setting status={status} leaves resolved_at as None.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status={status}.
        3. Assert response status is 200.
        4. Assert resolved_at is None in the response.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], status)
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_response_schema(body)
        assert body["resolved_at"] is None, (
            f"resolved_at should be None when status='{status}', got {body['resolved_at']}"
        )

    def test_notes_updated_with_status(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Notes field is updated when provided alongside status change.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with status='confirmed' and notes='verified by test'.
        3. Assert response status is 200.
        4. Assert response notes == 'verified by test'.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(
            created_finding["id"], "confirmed", notes="verified by test"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert_finding_response_schema(body)
        assert body["notes"] == "verified by test"

    @pytest.mark.xfail(reason="No status transition validation — resolved→open is accepted", strict=True)
    def test_status_transition_resolved_to_open_rejected(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Transitioning a resolved finding back to open should be rejected.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Set status to 'resolved'.
        3. Attempt to set status back to 'open'.
        4. Assert response status is 400 or 422.
        """
        dashboard_api_cl.update_finding_status_by_id(created_finding["id"], "resolved")
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], "open")
        assert resp.status_code in (400, 422), (
            "Transition from 'resolved' back to 'open' should be rejected"
        )

    @pytest.mark.parametrize("finding_id", [999999, 0, -1])
    def test_update_nonexistent_finding_returns_404(self, dashboard_api_cl: DashboardClient, finding_id):
        """Title: Updating status of a non-existent finding with id={finding_id} returns 404.

        Steps:
        1. Send PUT /findings/{finding_id}/status with status='confirmed'.
        2. Assert response status is 404.
        3. Assert error response body contains 'detail' field.
        """
        resp = dashboard_api_cl.update_finding_status_by_id(finding_id, "confirmed")
        assert resp.status_code == 404
        assert_error_response_schema(resp.json(), expected_fragment="not found")

    def test_update_missing_status_field_returns_422(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: PUT /findings/{id}/status with missing 'status' field returns 422.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send PUT /findings/{id}/status with an empty payload.
        3. Assert response status is 422.
        4. Assert response matches 422 schema.
        """
        resp = dashboard_api_cl.put(f"/findings/{created_finding['id']}/status", {})
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        error = resp.json()["detail"][0]
        assert error["loc"] == ["body", "status"], f"Unexpected loc: {error['loc']}"
        assert error["type"] == "missing", f"Unexpected type: {error['type']}"
        assert error["msg"] == "Field required", f"Unexpected msg: {error['msg']}"

    def test_update_dismissed_finding_returns_404(
        self, dashboard_api_cl: DashboardClient,
        finding_actions: FindingActions, created_finding
    ):
        """Title: Updating status of a dismissed finding returns 404.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Dismiss the finding.
        3. Send PUT /findings/{id}/status with status='confirmed'.
        4. Assert response status is 404.
        5. Assert error response body contains 'detail' field.
        """
        finding_id = created_finding["id"]
        finding_actions.dismiss(finding_id)
        resp = dashboard_api_cl.update_finding_status_by_id(finding_id, "confirmed")
        assert resp.status_code == 404
        assert_error_response_schema(resp.json(), expected_fragment="not found")

    def test_update_string_id_in_path_returns_422(self, dashboard_api_cl: DashboardClient):
        """Title: PUT /findings/{id}/status with a non-integer ID returns 422.

        Steps:
        1. Send PUT /findings/abc/status with a valid payload.
        2. Assert response status is 422.
        3. Assert error points to path param 'finding_id' with type 'int_parsing'.
        """
        resp = dashboard_api_cl.put("/findings/abc/status", {"status": "confirmed"})
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        error = resp.json()["detail"][0]
        assert error["loc"] == ["path", "finding_id"], f"Unexpected loc: {error['loc']}"
        assert error["type"] == "int_parsing", f"Unexpected type: {error['type']}"
        assert error["msg"] == "Input should be a valid integer, unable to parse string as an integer", (
            f"Unexpected msg: {error['msg']}"
        )

    def test_notes_preserved_when_not_provided_in_update(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: Existing notes are not cleared when status update omits notes field.

        Steps:
        1. Send POST /findings with notes='created by test fixture'.
        2. Update status to 'confirmed' without providing notes.
        3. Assert response status is 200.
        4. Assert notes field in response still equals original value.
        """
        original_notes = created_finding["notes"]
        resp = dashboard_api_cl.update_finding_status_by_id(created_finding["id"], "confirmed")
        assert resp.status_code == 200
        assert resp.json()["notes"] == original_notes

    def test_resolved_at_cleared_when_status_changes_from_resolved(
        self, dashboard_api_cl: DashboardClient, created_finding
    ):
        """Title: resolved_at is cleared in API response when status changes away from 'resolved'.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Set status to 'resolved' — assert resolved_at is not None.
        3. Set status to 'in_progress'.
        4. Assert resolved_at is None in the response.
        """
        finding_id = created_finding["id"]
        resolve_resp = dashboard_api_cl.update_finding_status_by_id(finding_id, "resolved")
        assert resolve_resp.json()["resolved_at"] is not None

        resp = dashboard_api_cl.update_finding_status_by_id(finding_id, "in_progress")
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is None


class TestDismissFinding:
    def test_dismiss_returns_204(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Dismissing a finding returns 204 No Content with empty body.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Send DELETE /findings/{id}.
        3. Assert response status is 204.
        4. Assert response body is empty.
        """
        resp = dashboard_api_cl.dismiss_finding_by_id(created_finding["id"])
        assert resp.status_code == 204
        assert resp.content == b"", f"Expected empty body for 204, got: {resp.content!r}"

    @pytest.mark.parametrize("finding_id", [999999, 0, -1])
    def test_dismiss_nonexistent_finding_returns_404(self, dashboard_api_cl: DashboardClient, finding_id):
        """Title: Dismissing a non-existent finding with id={finding_id} returns 404.

        Steps:
        1. Send DELETE /findings/{finding_id}.
        2. Assert response status is 404.
        3. Assert error response schema and detail contain 'not found'.
        """
        resp = dashboard_api_cl.dismiss_finding_by_id(finding_id)
        assert resp.status_code == 404
        assert_error_response_schema(resp.json(), expected_fragment="not found")

    def test_dismiss_already_dismissed_returns_404(self, dashboard_api_cl: DashboardClient, created_finding):
        """Title: Dismissing an already dismissed finding returns 404.

        Steps:
        1. Send POST /findings to create a new finding.
        2. Dismiss it via DELETE /findings/{id}.
        3. Dismiss the same finding again.
        4. Assert second response status is 404.
        5. Assert error response schema and detail contain 'not found'.
        """
        dashboard_api_cl.dismiss_finding_by_id(created_finding["id"])
        resp = dashboard_api_cl.dismiss_finding_by_id(created_finding["id"])
        assert resp.status_code == 404
        assert_error_response_schema(resp.json(), expected_fragment="not found")

    def test_dismiss_string_id_in_path_returns_422(self, dashboard_api_cl: DashboardClient):
        """Title: DELETE /findings/{id} with a non-integer ID returns 422.

        Steps:
        1. Send DELETE /findings/abc.
        2. Assert response status is 422.
        3. Assert error points to path param 'finding_id' with type 'int_parsing'.
        """
        resp = dashboard_api_cl.session.delete(dashboard_api_cl._url("/findings/abc"))
        assert resp.status_code == 422
        assert_422_response_schema(resp.json())
        error = resp.json()["detail"][0]
        assert error["loc"] == ["path", "finding_id"], f"Unexpected loc: {error['loc']}"
        assert error["type"] == "int_parsing", f"Unexpected type: {error['type']}"
        assert error["msg"] == "Input should be a valid integer, unable to parse string as an integer", (
            f"Unexpected msg: {error['msg']}"
        )


class TestSearchFindings:
    def test_search_by_cve_returns_results(self, dashboard_api_cl: DashboardClient, valid_vulnerability):
        """Title: Searching by CVE ID returns matching findings.

        Steps:
        1. Send GET /findings/search?q={valid_vulnerability cve_id}.
        2. Assert response status is 200.
        3. [Precondition] Assert results are non-empty.
        4. Assert all results match FindingSearchResult schema.
        5. Assert all results contain the CVE ID in the cve_id field.
        """
        cve_id = valid_vulnerability["cve_id"]
        resp = dashboard_api_cl.search_findings(cve_id)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0, f"Precondition failed: no search results for CVE '{cve_id}'"
        for result in results:
            assert_search_result_schema(result)
            assert cve_id in result["cve_id"]

    @pytest.mark.xfail(reason="Search returns cross-hostname results due to broken OR filter", strict=True)
    def test_search_by_hostname_returns_results(self, dashboard_api_cl: DashboardClient):
        """Title: Searching by hostname returns only findings for that host.

        Steps:
        1. Send GET /findings/search?q=prod-web-01.
        2. Assert response status is 200.
        3. Assert results are non-empty.
        4. Assert all results have hostname == 'prod-web-01'.
        """
        resp = dashboard_api_cl.search_findings("prod-web-01")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0
        for result in results:
            assert_search_result_schema(result)
        assert all(r["hostname"] == "prod-web-01" for r in results)

    def test_empty_query_returns_empty_list(self, dashboard_api_cl: DashboardClient):
        """Title: Empty search query returns an empty list.

        Steps:
        1. Send GET /findings/search?q=.
        2. Assert response status is 200.
        3. Assert response body is [].
        """
        resp = dashboard_api_cl.search_findings("")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize("query", [
        "CVE-9999-99999",          # EP: non-existent CVE
        "zzz-no-such-host",        # EP: non-existent hostname
        "!@#$%",                   # EP: special characters
        "PYTEST-NOMATCH-" + "X" * 185,  # BVA: very long string, guaranteed unique prefix
    ])
    def test_no_match_returns_empty_list(self, dashboard_api_cl: DashboardClient, query):
        """Title: Search with a non-matching query returns an empty list.

        Steps:
        1. Send GET /findings/search?q={query}.
        2. Assert response status is 200.
        3. Assert response body is [].
        """
        resp = dashboard_api_cl.search_findings(query)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_result_shape(self, dashboard_api_cl: DashboardClient):
        """Title: All search results match the FindingSearchResult schema.

        Steps:
        1. Send GET /findings/search?q=CVE.
        2. Assert response status is 200.
        3. [Precondition] Assert results are non-empty.
        4. Assert every result matches FindingSearchResult schema.
        """
        resp = dashboard_api_cl.search_findings("CVE")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0, "Precondition failed: no search results for query 'CVE'"
        for result in results:
            assert_search_result_schema(result)

    def test_search_by_notes_returns_matching_finding(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions,
        valid_asset, valid_vulnerability
    ):
        """Title: Searching by notes value returns the matching finding.

        Steps:
        1. Create a finding with a unique notes value.
        2. Send GET /findings/search?q={unique_notes}.
        3. Assert response status is 200.
        4. [Precondition] Assert results are non-empty.
        5. Assert the created finding ID appears in results.
        6. Assert all results match FindingSearchResult schema.
        """
        unique_notes = f"pytest-notes-search-{uuid.uuid4().hex}"
        finding = finding_actions.create(
            asset_id=valid_asset["id"],
            vulnerability_id=valid_vulnerability["id"],
            notes=unique_notes,
        )
        try:
            resp = dashboard_api_cl.search_findings(unique_notes)
            assert resp.status_code == 200
            results = resp.json()
            assert len(results) > 0, "Precondition failed: no results for unique notes query"
            result_ids = {r["finding_id"] for r in results}
            assert finding["id"] in result_ids, (
                f"Finding {finding['id']} not found in search results"
            )
            for result in results:
                assert_search_result_schema(result)
        finally:
            finding_actions.dismiss(finding["id"])

    def test_search_partial_match_returns_results(self, dashboard_api_cl: DashboardClient):
        """Title: Partial CVE ID substring returns matching findings (LIKE %q% behaviour).

        Steps:
        1. Send GET /findings/search?q=CVE-20 (partial prefix common to seeded CVEs).
        2. Assert response status is 200.
        3. [Precondition] Assert results are non-empty.
        4. Assert all cve_id values contain the search substring.
        5. Assert all results match FindingSearchResult schema.
        """
        partial = "CVE-20"
        resp = dashboard_api_cl.search_findings(partial)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0, f"Precondition failed: no results for partial query '{partial}'"
        for result in results:
            assert_search_result_schema(result)
            assert partial in result["cve_id"], (
                f"Expected '{partial}' in cve_id, got: {result['cve_id']}"
            )

    @pytest.mark.xfail(reason="Search endpoint does not filter dismissed findings — BUG", strict=True)
    def test_dismissed_finding_excluded_from_search(
        self, dashboard_api_cl: DashboardClient, finding_actions: FindingActions, valid_asset, valid_vulnerability
    ):
        """Title: Dismissed findings must not appear in search results.

        Steps:
        1. Create a finding with a unique notes value.
        2. Dismiss the finding.
        3. Search for the unique notes value.
        4. Assert the dismissed finding is not in results.
        """
        unique_notes = f"search-dismiss-test-{uuid.uuid4().hex}"
        finding = finding_actions.create(
            asset_id=valid_asset["id"],
            vulnerability_id=valid_vulnerability["id"],
            notes=unique_notes,
        )
        finding_actions.dismiss(finding["id"])

        resp = dashboard_api_cl.search_findings(unique_notes)
        assert resp.status_code == 200
        assert resp.json() == [], (
            f"Dismissed finding {finding['id']} should not appear in search results"
        )

    @pytest.mark.xfail(reason="Search endpoint is vulnerable to SQL injection via f-string", strict=True)
    def test_sql_injection_returns_no_results(self, dashboard_api_cl: DashboardClient):
        """Title: SQL injection payload should be treated as a literal string with no results.

        Steps:
        1. Send GET /findings/search?q=' OR '1'='1.
        2. Assert response status is 200.
        3. Assert response body is empty (input matched nothing literally).
        """
        resp = dashboard_api_cl.search_findings("' OR '1'='1")
        assert resp.status_code == 200
        assert len(resp.json()) == 0, (
            "Search should return 0 results for non-matching input"
        )