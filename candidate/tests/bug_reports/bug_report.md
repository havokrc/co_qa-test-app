# Bug Report — Vulnerability Management Dashboard

## Overview

During automated testing of the system (API, DB, Integration, UI), several functional and data integrity issues were identified.

Below is a list of confirmed bugs based on failing (xfail) test scenarios.

---

## 1. Pagination skips first asset

**Severity:** High

**Title:** First asset (id=1) is missing from first page of pagination

**Steps to reproduce:**
1. Send request: `GET /assets?page=1&per_page=10`
2. Extract asset IDs from response

**Expected behavior:**
- The first page should include the first asset (id=1)

**Actual behavior:**
- Asset with id=1 is missing from results

**Notes:**
- Likely off-by-one error in pagination logic

---

## 2. Pagination total count mismatch

**Severity:** High

**Title:** Pagination `items` count does not match `total`

**Steps to reproduce:**
1. Send request: `GET /assets?page=1&per_page=100`
2. Compare `len(items)` with `total`

**Expected behavior:**
- `len(items) == total` when all results fit on one page

**Actual behavior:**
- Mismatch between returned items and total count

---

## 3. Duplicate findings created on repeated scans

**Severity:** Critical

**Title:** Running identical scans creates duplicate findings

**Steps to reproduce:**
1. Run scan for asset with vulnerability `[X]`
2. Run the same scan again
3. Query findings for the asset

**Expected behavior:**
- Only one finding per `(asset_id, vulnerability_id)`

**Actual behavior:**
- Multiple duplicate findings are created

**Impact:**
- Data integrity issue
- Affects reporting and risk calculations

---

## 4. Dismissed findings still accessible

**Severity:** Medium

**Title:** Dismissed finding is still retrievable via API

**Steps to reproduce:**
1. Dismiss a finding via `DELETE /findings/{id}`
2. Request the same finding via `GET /findings/{id}`

**Expected behavior:**
- API should return `404 Not Found`

**Actual behavior:**
- Finding is still returned

---

## 5. Invalid status transition allowed

**Severity:** Medium

**Title:** Invalid status transition (resolved → open) is not rejected

**Steps to reproduce:**
1. Set finding status to `resolved`
2. Attempt to change status back to `open`

**Expected behavior:**
- API should reject invalid transition

**Actual behavior:**
- Transition is allowed or not properly validated

---

## 6. Search by hostname does not work

**Severity:** High

**Title:** Search endpoint does not return results for valid hostname

**Steps to reproduce:**
1. Send request: `GET /findings/search?q=<existing_hostname>`

**Expected behavior:**
- Findings related to hostname should be returned

**Actual behavior:**
- Empty result set returned

---

## 7. Potential SQL injection vulnerability in search

**Severity:** Critical

**Title:** Search endpoint may be vulnerable to SQL injection

**Steps to reproduce:**
1. Send request with payload:
   `GET /findings/search?q=' OR 1=1 --`

**Expected behavior:**
- Query should be safely handled (no results or sanitized input)

**Actual behavior:**
- Unexpected behavior (test indicates vulnerability)

**Notes:**
- Requires deeper security validation
- Likely missing parameterized queries

---

## 8. Risk score rounding is incorrect

**Severity:** Low

**Title:** Risk score is not properly rounded

**Steps to reproduce:**
1. Call `GET /stats/risk-score`
2. Inspect returned value

**Expected behavior:**
- Value should be rounded consistently (e.g., 2 decimal places)

**Actual behavior:**
- Rounding inconsistency detected

---

## 9. CVSS score constraint not enforced

**Severity:** High

**Title:** Database allows CVSS score outside valid range

**Steps to reproduce:**
1. Insert vulnerability with CVSS score outside [0, 10]

**Expected behavior:**
- DB constraint should reject invalid values

**Actual behavior:**
- Invalid values accepted

---

## 10. Invalid finding status accepted in DB

**Severity:** High

**Title:** Database allows invalid finding status values

**Steps to reproduce:**
1. Insert finding with arbitrary status string

**Expected behavior:**
- Only predefined enum values allowed

**Actual behavior:**
- Arbitrary values accepted

---

## 11. Invalid vulnerability severity accepted

**Severity:** Medium

**Title:** Database allows arbitrary severity values

**Steps to reproduce:**
1. Insert vulnerability with invalid severity

**Expected behavior:**
- Only valid severity values allowed

**Actual behavior:**
- Any string is accepted

---

## Summary

| Severity   | Count |
|------------|------|
| Critical   | 2    |
| High       | 5    |
| Medium     | 3    |
| Low        | 1    |

---

## Conclusion

The system demonstrates multiple issues across:
- Pagination logic
- Data integrity
- Business logic validation
- Security (potential SQL injection)

These issues should be prioritized before production use, especially:
- Duplicate findings
- SQL injection risk
- Missing DB constraints