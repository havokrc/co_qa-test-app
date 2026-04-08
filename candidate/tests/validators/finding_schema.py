"""JSON schema validators for finding-related API responses."""
# TODO:
#  - Validate datetime format (ISO 8601) for detected_at and resolved_at
#  - Validate resolved_at is None when status != "resolved"
#  - Validate vulnerability object structure inside FindingDetail
#  - Validate scanner field (str or None)
#  - Validate notes field (str or None)
#  - Add asset schema validator (for Scanner Service responses)

VALID_STATUSES = {"open", "confirmed", "in_progress", "resolved", "false_positive"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}

# Required fields and their expected types
_FINDING_RESPONSE_SCHEMA = {
    "id": int,
    "asset_id": int,
    "vulnerability_id": int,
    "status": str,
    "detected_at": str,
    "is_dismissed": bool,
}

_FINDING_DETAIL_SCHEMA = {
    **_FINDING_RESPONSE_SCHEMA,
    "asset_hostname": str,
    "vulnerability": dict,
}

_FINDING_SEARCH_RESULT_SCHEMA = {
    "finding_id": int,
    "status": str,
    "cve_id": str,
    "severity": str,
    "hostname": str,
}

_PAGINATED_FINDINGS_SCHEMA = {
    "items": list,
    "total": int,
    "page": int,
    "per_page": int,
}


def _validate(data: dict, schema: dict, context: str):
    errors = []
    for field, expected_type in schema.items():
        if field not in data:
            errors.append(f"missing field '{field}'")
        elif data[field] is not None and not isinstance(data[field], expected_type):
            errors.append(
                f"'{field}' expected {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
    assert not errors, f"{context} schema errors: {errors}"


def assert_valid_finding_response(data: dict):
    """Validate shape of a FindingResponse (list/create/update endpoints)."""
    _validate(data, _FINDING_RESPONSE_SCHEMA, "FindingResponse")
    assert data["status"] in VALID_STATUSES, (
        f"Invalid status '{data['status']}', expected one of {VALID_STATUSES}"
    )


def assert_valid_finding_detail(data: dict):
    """Validate shape of a FindingDetail (GET /findings/{id})."""
    _validate(data, _FINDING_DETAIL_SCHEMA, "FindingDetail")
    assert data["status"] in VALID_STATUSES, (
        f"Invalid status '{data['status']}', expected one of {VALID_STATUSES}"
    )


def assert_valid_search_result(data: dict):
    """Validate shape of a single search result (GET /findings/search)."""
    _validate(data, _FINDING_SEARCH_RESULT_SCHEMA, "FindingSearchResult")
    assert data["status"] in VALID_STATUSES, (
        f"Invalid status '{data['status']}'"
    )
    assert data["severity"] in VALID_SEVERITIES, (
        f"Invalid severity '{data['severity']}'"
    )


def assert_valid_paginated_findings(data: dict):
    """Validate shape of a paginated findings response."""
    _validate(data, _PAGINATED_FINDINGS_SCHEMA, "PaginatedFindings")
    assert data["total"] >= 0
    assert data["page"] >= 1
    assert data["per_page"] >= 1
    for item in data["items"]:
        assert_valid_finding_response(item)