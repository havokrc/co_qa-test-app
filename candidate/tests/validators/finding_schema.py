# JSON schema validators for finding-related API responses.
# TODO:
#  - Add asset schema validator (for Scanner Service responses)

from jsonschema import validate, FormatChecker

VALID_STATUSES = {"open", "confirmed", "in_progress", "resolved", "false_positive"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}

_VULNERABILITY_SCHEMA = {
    "type": "object",
    "required": ["id", "cve_id", "title", "severity", "created_at"],
    "properties": {
        "id":               {"type": "integer"},
        "cve_id":           {"type": "string"},
        "title":            {"type": "string"},
        "description":      {"type": ["string", "null"]},
        "severity":         {"type": "string", "enum": sorted(VALID_SEVERITIES)},
        "cvss_score":       {"type": ["number", "null"]},
        "published_date":   {"type": ["string", "null"], "format": "date-time"},
        "created_at":       {"type": "string", "format": "date-time"},
    },
}

_FINDING_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["id", "asset_id", "vulnerability_id", "status", "detected_at", "is_dismissed"],
    "properties": {
        "id":               {"type": "integer"},
        "asset_id":         {"type": "integer"},
        "vulnerability_id": {"type": "integer"},
        "status":           {"type": "string", "enum": sorted(VALID_STATUSES)},
        "detected_at":      {"type": "string", "format": "date-time"},
        "resolved_at":      {"type": ["string", "null"], "format": "date-time"},
        "scanner":          {"type": ["string", "null"]},
        "notes":            {"type": ["string", "null"]},
        "is_dismissed":     {"type": "boolean"},
    },
}

_FINDING_DETAIL_SCHEMA = {
    "allOf": [
        _FINDING_RESPONSE_SCHEMA,
        {
            "type": "object",
            "properties": {
                "asset_hostname": {"type": ["string", "null"]},
                "vulnerability": {
                    "oneOf": [{"type": "null"}, _VULNERABILITY_SCHEMA],
                },
            },
        },
    ],
}

_FINDING_SEARCH_RESULT_SCHEMA = {
    "type": "object",
    "required": ["finding_id", "status", "cve_id", "severity", "hostname"],
    "properties": {
        "finding_id": {"type": "integer"},
        "status":     {"type": "string", "enum": sorted(VALID_STATUSES)},
        "cve_id":     {"type": "string"},
        "severity":   {"type": "string", "enum": sorted(VALID_SEVERITIES)},
        "hostname":   {"type": "string"},
    },
}

_PAGINATED_FINDINGS_SCHEMA = {
    "type": "object",
    "required": ["items", "total", "page", "per_page"],
    "properties": {
        "items":    {"type": "array", "items": _FINDING_RESPONSE_SCHEMA},
        "total":    {"type": "integer", "minimum": 0},
        "page":     {"type": "integer", "minimum": 1},
        "per_page": {"type": "integer", "minimum": 1},
    },
}

_422_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {
        "detail": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["loc", "msg", "type"],
                "properties": {
                    "loc":  {"type": "array"},
                    "msg":  {"type": "string"},
                    "type": {"type": "string"},
                },
            },
        },
    },
}

_ERROR_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {
        "detail": {"type": "string"},
    },
}

_FORMAT_CHECKER = FormatChecker()


def assert_finding_response_schema(data: dict):
    """Assert data matches FindingResponse JSON schema (list/create/update endpoints)."""
    validate(instance=data, schema=_FINDING_RESPONSE_SCHEMA, format_checker=_FORMAT_CHECKER)


def assert_finding_detail_schema(data: dict):
    """Assert data matches FindingDetail JSON schema (GET /findings/{id})."""
    validate(instance=data, schema=_FINDING_DETAIL_SCHEMA, format_checker=_FORMAT_CHECKER)


def assert_search_result_schema(data: dict):
    """Assert data matches FindingSearchResult JSON schema (GET /findings/search)."""
    validate(instance=data, schema=_FINDING_SEARCH_RESULT_SCHEMA, format_checker=_FORMAT_CHECKER)


def assert_paginated_findings_schema(data: dict):
    """Assert data matches PaginatedFindings JSON schema."""
    validate(instance=data, schema=_PAGINATED_FINDINGS_SCHEMA, format_checker=_FORMAT_CHECKER)


def assert_422_response_schema(data: dict):
    """Assert data matches FastAPI 422 Unprocessable Entity JSON schema."""
    validate(instance=data, schema=_422_RESPONSE_SCHEMA, format_checker=_FORMAT_CHECKER)


def assert_error_response_schema(data: dict, expected_fragment: str = None):
    """Assert data matches error response JSON schema (detail: string).

    Optionally assert that the detail message contains expected_fragment.
    """
    validate(instance=data, schema=_ERROR_RESPONSE_SCHEMA, format_checker=_FORMAT_CHECKER)
    if expected_fragment:
        assert expected_fragment.lower() in data["detail"].lower(), (
            f"Expected '{expected_fragment}' in error detail, got: '{data['detail']}'"
        )
