import re
import pytest
from playwright.sync_api import Page, expect
from config.settings import DASHBOARD_URL
from clients.dashboard_client import DashboardClient
from clients.scanner_client import ScannerClient


@pytest.fixture(scope="module")
def browser_context_args(browser_context_args):
    """Slow down actions slightly for stability on CI."""
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------

def _load_dashboard(page: Page) -> None:
    page.goto(DASHBOARD_URL)
    page.wait_for_load_state("networkidle")


def _get_table_ids(page: Page) -> set[int]:
    """Return the set of finding IDs currently rendered in the findings table."""
    id_cells = page.locator("#findings-table tr td:first-child")
    ids = set()
    for i in range(id_cells.count()):
        text = id_cells.nth(i).inner_text().strip().lstrip("#")
        if text.isdigit():
            ids.add(int(text))
    return ids


def _table_is_empty(page: Page) -> bool:
    """Return True when the findings table shows the 'no results' placeholder row."""
    return page.locator("#findings-table td[colspan='8']").count() > 0


def _apply_filter(page: Page, filter_id: str, value: str) -> None:
    """Select a filter option and wait for the findings API response to complete."""
    with page.expect_response(
            lambda r: r.request.method == "GET" and "/findings" in r.url and r.status == 200, timeout=10_000,):
        page.locator(f"#{filter_id}").select_option(value=value)
        page.wait_for_load_state("networkidle")


def _change_first_finding_status(page: Page, status: str) -> int:
    """Change the status of the first finding in the table via the dropdown.

    Returns the finding ID so callers can verify persistence.
    """
    status_select = page.locator("select.status-select").first
    finding_id = _extract_finding_id(status_select)
    with page.expect_response(
        lambda r: f"/findings/{finding_id}/status" in r.url and r.status == 200,
        timeout=10_000,
    ):
        status_select.select_option(value=status)
    return finding_id


def _extract_finding_id(select_locator) -> int:
    """Extract finding ID from status select onchange attribute.

    The select renders as: onchange="updateStatus(123, this.value)"
    """
    onchange = select_locator.get_attribute("onchange")
    match = re.search(r"updateStatus\((\d+),", onchange)
    assert match, f"Could not extract finding ID from onchange: {onchange}"
    return int(match.group(1))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFindingsTableData:
    def test_findings_table_has_rows(self, page: Page):
        """Title: Findings table loads and displays at least one row.

        Steps:
        1. Navigate to dashboard and wait for full network idle.
        2. Assert findings table contains at least one row.
        """
        _load_dashboard(page)

        table = page.locator("#findings-table")
        expect(table).to_be_visible(timeout=10_000)

        table_ids = _get_table_ids(page)
        assert len(table_ids) > 0, "Findings table contains no data rows"

    def test_findings_table_ids_match_api(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Finding IDs visible in table match IDs returned by API.

        Steps:
        1. Fetch findings from API (first page, per_page=50).
        2. Navigate to dashboard and wait for network idle.
        3. Extract IDs from table rows (format: #<id>).
        4. Assert the set of table IDs equals the set of API IDs.
        """
        api_resp = dashboard_api_cl.list_findings(per_page=50)
        assert api_resp.status_code == 200
        api_ids = {f["id"] for f in api_resp.json()["items"]}

        _load_dashboard(page)

        assert _get_table_ids(page) == api_ids

    def test_findings_table_statuses_match_api(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Status badges in table match statuses returned by API.

        Steps:
        1. Fetch findings from API and build id→status map.
        2. Navigate to dashboard and wait for network idle.
        3. For each row, extract finding ID and status badge text (UI renders underscores as spaces, e.g. 'in_progress' → 'in progress').
        4. Normalize badge text back to underscore format and assert it matches the API value.
        """
        api_resp = dashboard_api_cl.list_findings(per_page=50)
        assert api_resp.status_code == 200
        api_findings = {f["id"]: f["status"] for f in api_resp.json()["items"]}

        _load_dashboard(page)

        rows = page.locator("#findings-table tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            id_text = row.locator("td:nth-child(1)").inner_text().strip().lstrip("#")
            if not id_text.isdigit():
                continue
            finding_id = int(id_text)
            # UI renders status with underscores replaced: "in_progress" → "in progress"
            ui_status = row.locator("span.status").inner_text().strip().replace(" ", "_")
            assert ui_status == api_findings[finding_id], (
                f"Finding #{finding_id}: UI shows '{ui_status}', API has '{api_findings[finding_id]}'"
            )

    def test_findings_table_asset_ids_match_api(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Asset IDs in table match those returned by API.

        Steps:
        1. Fetch findings from API and build id→asset_id map.
        2. Navigate to dashboard and wait for network idle.
        3. For each row, extract finding ID and asset_id column value.
        4. Assert asset_id matches API value for that finding.
        """
        api_findings = {
            f["id"]: f["asset_id"]
            for f in dashboard_api_cl.list_findings(per_page=50).json()["items"]
        }

        _load_dashboard(page)

        rows = page.locator("#findings-table tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            id_text = row.locator("td:nth-child(1)").inner_text().strip().lstrip("#")
            if not id_text.isdigit():
                continue
            finding_id = int(id_text)
            asset_id_text = row.locator("td:nth-child(6)").inner_text().strip()
            assert int(asset_id_text) == api_findings[finding_id], (
                f"Finding #{finding_id}: UI shows asset_id={asset_id_text}, "
                f"API has {api_findings[finding_id]}"
            )


class TestStatusChangeFlow:
    def test_status_change_shows_success_message(self, page: Page):
        """Title: Changing status via dropdown shows correct success message.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Change the first finding's status to 'confirmed'.
        3. Assert success message is visible and contains finding ID and new status.
        """
        _load_dashboard(page)
        finding_id = _change_first_finding_status(page, "confirmed")

        msg = page.locator(".message-success")
        expect(msg).to_be_visible(timeout=5_000)
        assert f"Finding #{finding_id}" in msg.inner_text()
        assert "confirmed" in msg.inner_text()

    def test_status_change_persists_in_api(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Status change via UI dropdown is reflected in API response.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Change the first finding's status to 'in_progress'.
        3. Fetch the finding via API and assert status equals 'in_progress'.
        """
        _load_dashboard(page)
        finding_id = _change_first_finding_status(page, "in_progress")

        api_resp = dashboard_api_cl.get_finding_by_id(finding_id)
        assert api_resp.status_code == 200
        assert api_resp.json()["status"] == "in_progress"

    def test_status_change_persists_in_db(self, page: Page, db):
        """Title: Status change via UI dropdown is persisted in the database.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Change the first finding's status to 'resolved'.
        3. Query DB directly and assert status equals 'resolved'.
        """
        _load_dashboard(page)
        finding_id = _change_first_finding_status(page, "resolved")

        db.execute("SELECT status FROM findings WHERE id = %s", (finding_id,))
        assert db.fetchone()["status"] == "resolved"


    @pytest.mark.xfail(
        strict=True,
        reason="BUG: Status badge in table does not update after dropdown change — UI does not re-render the span",
    )
    def test_status_badge_updates_in_table_after_change(self, page: Page, dashboard_api_cl):
        """Title: Status badge in row should reflect new status after dropdown change.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Reset the first finding to 'open' via API to ensure a known initial state.
        3. Reload dashboard so badge reflects 'open'.
        4. Change status to 'confirmed' via the dropdown on the first row.
        5. Assert API confirms status equals 'confirmed'.
        6. Assert the status badge in that row updates to 'confirmed'.
        """
        _load_dashboard(page)

        first_row = page.locator("#findings-table tr").first
        status_select = first_row.locator("select.status-select")
        finding_id = _extract_finding_id(status_select)

        dashboard_api_cl.update_finding_status_by_id(finding_id, "open")
        _load_dashboard(page)

        first_row = page.locator("#findings-table tr").first
        status_select = first_row.locator("select.status-select")

        with page.expect_response(
            lambda r: f"/findings/{finding_id}/status" in r.url and r.status == 200,
            timeout=10_000,
        ):
            status_select.select_option(value="confirmed")

        api_resp = dashboard_api_cl.get_finding_by_id(finding_id)
        assert api_resp.status_code == 200
        assert api_resp.json()["status"] == "confirmed"

        expect(first_row.locator("span.status")).to_have_text("confirmed", timeout=5_000)


class TestRefreshButton:
    def test_refresh_button_reloads_findings_table(self, page: Page):
        """Title: Refresh button triggers API call and table remains populated.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Count rows before refresh.
        3. Click Refresh button and wait for /findings API response.
        4. Assert table still has rows after reload.
        """
        _load_dashboard(page)
        assert page.locator("#findings-table tr").count() > 0

        with page.expect_response(lambda r: "/findings" in r.url, timeout=10_000):
            page.locator("button.btn-primary", has_text="Refresh").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("#findings-table tr").first).to_be_visible()
        assert page.locator("#findings-table tr").count() > 0

    def test_refresh_button_reflects_latest_api_data(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: After clicking Refresh, table IDs match current API state.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Click Refresh button and wait for API response.
        3. Fetch findings from API.
        4. Assert table IDs match API IDs.
        """
        _load_dashboard(page)

        with page.expect_response(lambda r: "/findings" in r.url, timeout=10_000):
            page.locator("button.btn-primary", has_text="Refresh").click()
        page.wait_for_load_state("networkidle")

        api_resp = dashboard_api_cl.list_findings(per_page=50)
        assert api_resp.status_code == 200
        api_ids = {f["id"] for f in api_resp.json()["items"]}
        assert _get_table_ids(page) == api_ids


class TestSummaryCards:
    def test_summary_cards_match_api_stats(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Summary card counts match /stats/summary API response.

        Steps:
        1. Fetch /stats/summary from API.
        2. Navigate to dashboard and wait for network idle.
        3. Assert each card value (#critical-count, #high-count, etc.) matches API.
        4. Assert active count equals total - resolved - false_positive.
        """
        stats = dashboard_api_cl.summary().json()
        expected_active = (
            stats["total_findings"]
            - stats["resolved_findings"]
            - stats["false_positive_findings"]
        )

        _load_dashboard(page)

        assert int(page.locator("#total-count").inner_text()) == expected_active
        assert int(page.locator("#critical-count").inner_text()) == stats["by_severity"].get("critical", 0)
        assert int(page.locator("#high-count").inner_text()) == stats["by_severity"].get("high", 0)
        assert int(page.locator("#medium-count").inner_text()) == stats["by_severity"].get("medium", 0)
        assert int(page.locator("#low-count").inner_text()) == stats["by_severity"].get("low", 0)


class TestFiltering:
    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low"])
    def test_filter_by_severity_shows_only_matching_rows(self, page: Page, severity: str):
        """Title: Severity filter shows only rows with the selected severity.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Select severity in #filter-severity and wait for /findings API response.
        3. If no rows appear, skip (no data for this severity).
        4. Assert every row's severity badge matches the selected severity.
        """
        _load_dashboard(page)
        _apply_filter(page, "filter-severity", severity)

        if _table_is_empty(page):
            pytest.skip(f"No findings with severity={severity} in current dataset")

        rows = page.locator("#findings-table tr")
        for i in range(rows.count()):
            expect(rows.nth(i).locator("span.severity")).to_have_text(severity, timeout=3_000)

    @pytest.mark.parametrize("status", ["open", "confirmed", "in_progress", "resolved", "false_positive"])
    def test_filter_by_status_shows_only_matching_rows(self, page: Page, status: str):
        """Title: Status filter shows only rows with the selected status.

        Steps:
        1. Navigate to dashboard and wait for network idle.
        2. Select status in #filter-status and wait for /findings API response.
        3. If no rows appear, skip (no data for this status).
        4. Assert every row's status badge matches the selected status.
        """
        _load_dashboard(page)
        _apply_filter(page, "filter-status", status)

        if _table_is_empty(page):
            pytest.skip(f"No findings with status={status} in current dataset")

        expected_text = status.replace("_", " ")
        rows = page.locator("#findings-table tr")
        for i in range(rows.count()):
            expect(rows.nth(i).locator("span.status")).to_have_text(expected_text, timeout=3_000)

    def test_clearing_filter_restores_all_findings(self, page: Page, dashboard_api_cl: DashboardClient):
        """Title: Clearing a filter restores the full unfiltered findings list.

        Steps:
        1. Navigate to dashboard, apply severity=critical filter.
        2. Clear severity filter (select empty option).
        3. Assert table IDs match full API response.
        """
        _load_dashboard(page)
        _apply_filter(page, "filter-severity", "critical")
        _apply_filter(page, "filter-severity", "")

        api_resp = dashboard_api_cl.list_findings(per_page=50)
        assert api_resp.status_code == 200
        api_ids = {f["id"] for f in api_resp.json()["items"]}
        assert _get_table_ids(page) == api_ids


class TestAssetsTable:
    @pytest.mark.xfail(
        strict=True,
        reason="BUG: Assets table on dashboard is always empty — UI does not load assets from Scanner API",
    )
    def test_assets_table_has_rows(self, page: Page, scanner_api_cl: ScannerClient):
        """Title: Assets table on dashboard loads and displays rows matching Scanner API.

        Steps:
        1. Fetch assets from Scanner API GET /assets.
        2. Navigate to dashboard and wait for network idle.
        3. Assert #assets-table contains at least one row.
        4. Extract hostnames from table rows.
        5. Assert at least one hostname from the API appears in the table.
        """
        api_hostnames = {
            a["hostname"]
            for a in scanner_api_cl.list_assets(page=1, per_page=50).json()["items"]
        }
        assert api_hostnames, "Precondition failed: Scanner API returned no assets"

        _load_dashboard(page)

        rows = page.locator("#assets-table tr")
        assert rows.count() > 0, "Assets table is empty — no rows rendered"

        ui_hostnames = set()
        for i in range(rows.count()):
            text = rows.nth(i).locator("td:first-child").inner_text().strip()
            if text:
                ui_hostnames.add(text)

        assert ui_hostnames & api_hostnames, (
            f"No API hostnames found in assets table. "
            f"API: {api_hostnames} | UI: {ui_hostnames}"
        )
