import pytest
from clients.dashboard_client import DashboardClient
from clients.scanner_client import ScannerClient
from clients.db_client import DBClient


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_cl() -> DashboardClient:
    """Dashboard API client (port 8000)."""
    return DashboardClient()


@pytest.fixture(scope="session")
def scanner_cl() -> ScannerClient:
    """Scanner Service client (port 8001)."""
    return ScannerClient()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "qa_test",
    "user": "qa_user",
    "password": "qa_password",
}

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
# Data helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def created_finding(api_cl: DashboardClient):
    """Create a fresh finding for a test and clean it up afterwards.

    Yields the full JSON response dict of the created finding.
    Uses seed asset_id=1 (prod-web-01) and vulnerability_id=1 (Log4Shell).
    """
    resp = api_cl.create_finding(
        asset_id=1,
        vulnerability_id=1,
        scanner="pytest",
        notes="created by test fixture",
    )
    assert resp.status_code == 201, f"Fixture setup failed: {resp.text}"
    finding = resp.json()
    yield finding
    # best-effort cleanup: dismiss the finding if it still exists
    api_cl.dismiss_finding_by_id(finding["id"])


@pytest.fixture
def created_asset(scanner_cl: ScannerClient):
    """Create a temporary asset and deactivate it after the test."""
    resp = scanner_cl.create_asset(
        hostname="test-asset-fixture",
        asset_type="server",
        environment="development",
        ip_address="10.99.0.1",
        os="Ubuntu 22.04",
    )
    assert resp.status_code == 201, f"Fixture setup failed: {resp.text}"
    asset = resp.json()
    yield asset
    scanner_cl.deactivate_asset_by_id(asset["id"])