# Bug Report — Vulnerability Management Dashboard

## Overview

All bugs below are confirmed by automated tests marked `xfail(strict=True)`.
Each entry includes the covering test for traceability.

---

## BUG-01 · SQL Injection in Search Endpoint

**Severity:** Critical
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestSearchFindings::test_sql_injection_returns_no_results`

**Steps to reproduce:**
1. Send `GET /findings/search?q=' OR '1'='1`

**Expected:** Empty results — input treated as literal string.

**Actual:** Query returns all findings — SQL is injected directly into query via f-string interpolation.

**Root cause:** Search endpoint builds raw SQL with f-string instead of parameterized queries.

---

## BUG-02 · Duplicate Findings on Repeated Scans

**Severity:** Critical
**Service:** Scanner Service
**Tests:**
- `test_integration.py::TestDuplicateFindings::test_running_same_scan_twice_does_not_create_duplicates`
- `test_integration.py::TestConcurrentScans::test_concurrent_scans_do_not_create_duplicate_findings`

**Steps to reproduce:**
1. Run `POST /scans` for asset X with vulnerability Y
2. Run the same scan again (or concurrently from multiple threads)
3. Query `GET /findings?asset_id=X`

**Expected:** One finding per `(asset_id, vulnerability_id)`.

**Actual:** Multiple duplicate findings created — no deduplication or locking on insert.

**Impact:** Data integrity failure, inflated risk scores, broken reporting.

---

## BUG-03 · Dismissed Finding Still Accessible via GET

**Severity:** High
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestGetFinding::test_dismissed_finding_returns_404`

**Steps to reproduce:**
1. Send `DELETE /findings/{id}` — receives 204
2. Send `GET /findings/{id}`

**Expected:** 404 Not Found.

**Actual:** 200 OK — dismissed finding is still returned.

---

## BUG-04 · Search Endpoint Returns Dismissed Findings

**Severity:** High
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestSearchFindings::test_dismissed_finding_excluded_from_search`

**Steps to reproduce:**
1. Create a finding with unique notes value
2. Dismiss it via `DELETE /findings/{id}`
3. Send `GET /findings/search?q=<unique_notes>`

**Expected:** Empty list — dismissed findings excluded.

**Actual:** Dismissed finding appears in search results.

---

## BUG-05 · Search by Hostname Returns Wrong Results (Broken OR Filter)

**Severity:** High
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestSearchFindings::test_search_by_hostname_returns_results`

**Steps to reproduce:**
1. Send `GET /findings/search?q=prod-web-01`

**Expected:** Only findings whose asset hostname is `prod-web-01`.

**Actual:** Returns findings across all hostnames — search uses OR across all fields, not hostname-scoped.

---

## BUG-06 · Scanner Pagination Skips First Asset

**Severity:** High
**Service:** Scanner Service
**Test:** `test_integration.py::TestAssetPagination::test_first_page_includes_first_asset`

**Steps to reproduce:**
1. Send `GET /assets?page=1&per_page=10`
2. Check if asset with id=1 (`prod-web-01`) is in results

**Expected:** First asset appears on page 1.

**Actual:** Asset id=1 is missing — off-by-one in pagination offset.

---

## BUG-07 · Scanner Pagination Total Count Mismatch

**Severity:** High
**Service:** Scanner Service
**Test:** `test_integration.py::TestAssetPagination::test_items_count_matches_total_on_single_page`

**Steps to reproduce:**
1. Send `GET /assets?page=1&per_page=100`
2. Compare `len(items)` with `total`

**Expected:** `len(items) == total` when all results fit on one page.

**Actual:** `items` count does not match `total` field.

---

## BUG-08 · Scanner Field Has No Length Validation

**Severity:** High
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestCreateFinding::test_create_scanner_over_max_length_returns_422`

**Steps to reproduce:**
1. Send `POST /findings` with `scanner` value of 101+ characters

**Expected:** 422 Unprocessable Entity with validation error.

**Actual:** Request passes Pydantic validation and hits the DB `String(100)` column limit — may cause 500 Internal Server Error.

---

## BUG-09 · Assets Table Empty on Dashboard UI

**Severity:** High
**Service:** Dashboard UI
**Test:** `test_ui_smoke.py::TestAssetsTable::test_assets_table_has_rows`

**Steps to reproduce:**
1. Open `http://localhost:8000/`
2. Scroll to the Assets section

**Expected:** Assets table populated from Scanner API.

**Actual:** `<tbody id="assets-table">` is always empty — UI never loads asset data.

---

## BUG-10 · Invalid Status Transition Not Rejected

**Severity:** Medium
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestUpdateFindingStatus::test_status_transition_resolved_to_open_rejected`

**Steps to reproduce:**
1. Set finding status to `resolved`
2. Send `PUT /findings/{id}/status` with `{"status": "open"}`

**Expected:** 400 or 422 — backward transition should be rejected.

**Actual:** Transition accepted — no state machine validation.

---

## BUG-11 · Search Does Not Filter by asset_id=0

**Severity:** Low
**Service:** Dashboard API
**Test:** `test_api_validation.py::TestListFindings::test_filter_by_asset_id_returns_empty_for_unknown[0]`

**Steps to reproduce:**
1. Send `GET /findings?asset_id=0`

**Expected:** Empty list — no asset with id=0 exists.

**Actual:** Returns all findings — `asset_id=0` filter is ignored by the service.

---

## BUG-12 · Status Badge Not Updated After UI Status Change

**Severity:** Low
**Service:** Dashboard UI
**Test:** `test_ui_smoke.py::TestStatusChangeFlow::test_status_badge_updates_in_table_after_change`

**Steps to reproduce:**
1. Open `http://localhost:8000/`
2. Change a finding's status via the dropdown
3. Observe the status badge in the same row

**Expected:** Badge text updates to reflect the new status.

**Actual:** Badge retains the old status text — UI does not re-render the `<span class="status">` after the API call succeeds.

---

## 📌 Out of Scope — Found in Source Code Review

The following issue was identified by reviewing application source code directly.
It falls outside the explicit task requirements (Part 1 focused on Findings CRUD, error handling, and search),
but is documented here for completeness.

### Risk Score Float Precision (`GET /stats/risk-score`)

**Severity:** Low
**Service:** Dashboard API
**Source:** `services/dashboard-api/app/routes/stats.py:35` — `# BUG #5`

**Description:** The risk score calculation accumulates CVSS scores using Python `float` instead of `Decimal`,
and returns an unrounded result. This can produce values like `7.333333333333334` instead of `7.33`.

**Expected:** Risk score and average CVSS values rounded to a consistent precision (e.g. 2 decimal places).

**Actual:** Raw floating point result returned — no rounding applied.

**Note:** `GET /stats/risk-score` is listed in the API Reference but testing it was not an explicit task requirement.
No automated test covers this endpoint in the current suite.

---

## ⚠ Risks — Missing Database-Level Constraints

The following are not confirmed bugs in the current data, but represent **architectural risks**.
The application enforces these rules at the API layer only. A direct database write (migration script,
admin tool, or compromised connection) would bypass all validation silently.

Current data is clean — the tests in `TestDataIntegrity` pass — but no DB-level constraint prevents future corruption.

| Risk | Table | Column | Missing Constraint | Impact if violated |
|------|-------|--------|--------------------|--------------------|
| RISK-01 | `vulnerabilities` | `cvss_score` | `CHECK (cvss_score >= 0 AND cvss_score <= 10)` | Invalid scores accepted, risk calculations corrupted |
| RISK-02 | `findings` | `status` | `CHECK (status IN ('open', 'confirmed', 'in_progress', 'resolved', 'false_positive'))` | Arbitrary strings stored, filters and reports break |
| RISK-03 | `vulnerabilities` | `severity` | `CHECK (severity IN ('critical', 'high', 'medium', 'low'))` | Arbitrary strings stored, severity filters break |

**Recommendation:** Add `CHECK` constraints (or PostgreSQL `ENUM` types) at the DB schema level so data integrity is enforced independently of the application.

---

## Summary

| ID     | Severity | Service        | Title                                            |
|--------|----------|----------------|--------------------------------------------------|
| BUG-01 | Critical | Dashboard API | SQL injection in search endpoint |
| BUG-02 | Critical | Scanner Service | Duplicate findings on repeated/concurrent scans |
| BUG-03 | High | Dashboard API | Dismissed finding accessible via GET |
| BUG-04 | High | Dashboard API | Search returns dismissed findings |
| BUG-05 | High | Dashboard API | Search by hostname returns wrong results |
| BUG-06 | High | Scanner Service | Pagination skips first asset |
| BUG-07 | High | Scanner Service | Pagination total count mismatch |
| BUG-08 | High | Dashboard API | Scanner field has no length validation |
| BUG-09 | High | Dashboard UI | Assets table empty on dashboard |
| BUG-10 | Medium | Dashboard API | Invalid status transition not rejected |
| BUG-11 | Low | Dashboard API | asset_id=0 filter ignored |
| BUG-12 | Low | Dashboard UI | Status badge not updated after UI change |

**Total: 12 bugs — 2 Critical · 7 High · 1 Medium · 2 Low**
