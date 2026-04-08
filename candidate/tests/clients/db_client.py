"""Database client wrapping psycopg2 for direct DB access in tests."""
import psycopg2
import psycopg2.extras


class DBClient:
    def __init__(self, config: dict = None):
        self._config = config
        self._conn = psycopg2.connect(**self._config)
        self._conn.autocommit = False

    # --- Connection lifecycle ---

    def close(self):
        self._conn.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def cursor(self):
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # --- Query helpers ---

    def fetchone(self, sql: str, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params)

    # --- Domain helpers ---

    def get_finding_by_id(self, finding_id: int):
        return self.fetchone(f"SELECT * FROM findings WHERE id = {finding_id}")

    def get_asset_by_id(self, asset_id: int):
        return self.fetchone(f"SELECT * FROM assets WHERE id = {asset_id}")

    def get_vulnerability_by_id(self, vuln_id: int):
        return self.fetchone(f"SELECT * FROM vulnerabilities WHERE id = {vuln_id}")

    def get_findings_by_asset_id(self, asset_id: int):
        return self.fetchall(f"SELECT * FROM findings WHERE asset_id = {asset_id}")

    def get_scans_by_asset_id(self, asset_id: int):
        return self.fetchall(f"SELECT * FROM scans WHERE asset_id = {asset_id}")