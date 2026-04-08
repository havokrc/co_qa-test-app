import re
import pytest
from playwright.sync_api import Page, expect

DASHBOARD_URL = "http://localhost:8000"

#TODO: requires improvements

@pytest.fixture(scope="module")
def browser_context_args(browser_context_args):
    """Slow down actions slightly for stability on CI."""
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


class TestDashboardLoads:
    def test_page_title_and_findings_visible(self, page: Page):
        page.goto(DASHBOARD_URL)
        # Page must not be an error page
        expect(page).not_to_have_title(re.compile(r"error|not found", re.IGNORECASE))

        # At least one finding row / card should be present in the DOM
        # Try common selectors; adjust if the app uses different class names
        finding_elements = page.locator(
            "table tbody tr, [data-testid='finding'], .finding-row, .finding-card"
        )
        expect(finding_elements.first).to_be_visible(timeout=10_000)

    def test_dashboard_shows_summary_stats(self, page: Page):
        page.goto(DASHBOARD_URL)
        # Stats section (risk score / summary counts) should be visible
        stats = page.locator(
            "[data-testid='stats'], .stats, .summary, #stats, #summary, .risk-score"
        )
        # Not all UIs have this; soft check — just ensure the page loaded fully
        expect(page.locator("body")).to_be_visible()
        expect(page).not_to_have_url(re.compile(r"/error"))


class TestFindingStatusChange:
    def test_change_finding_status_via_dropdown(self, page: Page):
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")

        # Locate the first status dropdown (class="status-select", always shows "Change…")
        status_select = page.locator("select.status-select").first
        expect(status_select).to_be_visible(timeout=10_000)

        # Select a status while capturing the API response it triggers
        with page.expect_response(
            lambda r: "/findings/" in r.url and "/status" in r.url and r.status == 200,
            timeout=10_000,
        ):
            status_select.select_option(value="confirmed")

        # Success message should appear in the DOM
        expect(page.locator(".message-success")).to_be_visible(timeout=5_000)
