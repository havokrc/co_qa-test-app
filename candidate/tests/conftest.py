import uuid
import pytest
from clients.dashboard_client import DashboardClient
from clients.scanner_client import ScannerClient
from clients.db_client import DBClient
from config.settings import DB_CONFIG
from services.finding_actions import FindingActions
from data_builders.asset_payloads import AssetPayloadBuilder


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def dashboard_api_cl() -> DashboardClient:
    """Dashboard API client (port 8000)."""
    return DashboardClient()


@pytest.fixture(scope="session")
def scanner_api_cl() -> ScannerClient:
    """Scanner Service client (port 8001)."""
    return ScannerClient()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_client():
    """Session-scoped DBClient instance."""
    client = DBClient(config=DB_CONFIG)
    yield client
    client.close()


@pytest.fixture
def db(db_client: DBClient):
    """Function-scoped cursor with automatic rollback after each test.

    Use this when you need to query the DB without leaving side effects.
    For tests that need committed data visible to the API, use db_client directly
    and handle cleanup manually.
    """
    cursor = db_client.cursor()
    yield cursor
    db_client.rollback()
    cursor.close()


# ---------------------------------------------------------------------------
# Dynamic seed data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def valid_asset(scanner_api_cl: ScannerClient):
    """Return the first active asset, creating a temporary one if none exist.

    Session-scoped: shared stable reference for the whole test run.
    If created by this fixture, it is deactivated at session teardown.
    DELETE /assets/{id} → 204 on success (per OpenAPI spec).
    404 accepted in teardown as a safe idempotent fallback.
    """
    resp = scanner_api_cl.list_assets(page=1, per_page=10)
    assert resp.status_code == 200, f"Failed to fetch assets: {resp.text}"
    items = resp.json()["items"]
    if items:
        yield items[0]
        return

    create_resp = scanner_api_cl.create_asset(AssetPayloadBuilder.create(
        hostname=f"auto-asset-{uuid.uuid4().hex[:8]}"
    ))
    assert create_resp.status_code == 201, f"Failed to create fallback asset: {create_resp.text}"
    asset = create_resp.json()
    yield asset
    cleanup_resp = scanner_api_cl.deactivate_asset_by_id(asset["id"])
    assert cleanup_resp.status_code in (204, 404), (
        f"Teardown failed for auto-created asset {asset['id']}: {cleanup_resp.status_code}"
    )


@pytest.fixture(scope="session")
def valid_vulnerability(dashboard_api_cl: DashboardClient):
    """Return the first vulnerability from the catalog.

    Session-scoped and read-only — vulnerabilities cannot be created via API,
    so this asserts at least one exists in the seed data.
    GET /vulnerabilities returns a plain list (not paginated).
    """
    resp = dashboard_api_cl.list_vulnerabilities()
    assert resp.status_code == 200, f"Failed to fetch vulnerabilities: {resp.text}"
    items = resp.json()
    assert len(items) > 0, "No vulnerabilities in catalog — seed data may be missing"
    return items[0]


@pytest.fixture(scope="session")
def valid_vulnerability_ids(dashboard_api_cl: DashboardClient):
    """Return up to 6 vulnerability IDs from the catalog for use in scan tests.

    Session-scoped and read-only — asserts at least 2 exist.
    GET /vulnerabilities returns a plain list (not paginated).
    """
    resp = dashboard_api_cl.list_vulnerabilities()
    assert resp.status_code == 200, f"Failed to fetch vulnerabilities: {resp.text}"
    items = resp.json()
    assert len(items) >= 2, "Need at least 2 vulnerabilities in catalog to run scan tests"
    return [v["id"] for v in items[:6]]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def finding_actions(dashboard_api_cl: DashboardClient) -> FindingActions:
    """FindingActions instance bound to the Dashboard API client."""
    return FindingActions(dashboard_api_cl)


@pytest.fixture(scope="session", autouse=True)
def seeded_findings(dashboard_api_cl: DashboardClient, valid_asset):
    """Pre-create 2 findings per status per severity for the test session.

    Fetches vulnerabilities grouped by severity, then for each severity creates
    2 findings per status (open, confirmed, in_progress, resolved, false_positive).
    All created findings are dismissed at session teardown.
    """
    actions = FindingActions(dashboard_api_cl)
    statuses = ["open", "confirmed", "in_progress", "resolved", "false_positive"]

    by_severity = {}
    for v in dashboard_api_cl.list_vulnerabilities().json():
        by_severity.setdefault(v["severity"], v["id"])

    created = []
    for vuln_id in by_severity.values():
        for status in statuses:
            for _ in range(2):
                f = actions.create(asset_id=valid_asset["id"], vulnerability_id=vuln_id)
                if status != "open":
                    actions.update_status(f["id"], status)
                created.append(f)

    yield

    for f in created:
        actions.dismiss(f["id"])


@pytest.fixture
def created_finding(finding_actions: FindingActions, valid_asset, valid_vulnerability):
    """Create a fresh finding for a test and clean it up afterwards.

    Yields the full JSON response dict of the created finding.
    DELETE /findings/{id} → 204 on success (per OpenAPI spec).
    404 accepted in teardown as a safe idempotent fallback.
    """
    finding = finding_actions.create(
        asset_id=valid_asset["id"],
        vulnerability_id=valid_vulnerability["id"],
        notes="created by test fixture",
    )
    yield finding
    finding_actions.dismiss(finding["id"])


@pytest.fixture
def created_asset(scanner_api_cl: ScannerClient):
    """Create a temporary asset with a unique hostname and deactivate it after the test.

    DELETE /assets/{id} → 204 on success (per OpenAPI spec).
    404 accepted in teardown as a safe idempotent fallback.
    """
    unique_hostname = f"test-asset-{uuid.uuid4().hex[:8]}"
    resp = scanner_api_cl.create_asset(AssetPayloadBuilder.create(hostname=unique_hostname))
    assert resp.status_code == 201, f"Fixture setup failed: {resp.text}"
    asset = resp.json()
    yield asset
    # TODO: scan-generated findings for this asset are not dismissed on teardown,
    #       causing undismissed finding rows to accumulate in DB across test runs.
    #       Fix: fetch GET /findings?asset_id={id} and dismiss each before deactivating.
    cleanup_resp = scanner_api_cl.deactivate_asset_by_id(asset["id"])
    assert cleanup_resp.status_code in (204, 404), (
        f"Fixture teardown failed for asset {asset['id']}: {cleanup_resp.status_code}"
    )
