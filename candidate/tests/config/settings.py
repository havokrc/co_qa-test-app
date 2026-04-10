"""Central configuration — all values read from environment variables with localhost defaults."""
import os

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000")
SCANNER_URL = os.getenv("SCANNER_URL", "http://localhost:8001")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "dbname": os.getenv("DB_NAME", "qa_test"),
    "user": os.getenv("DB_USER", "qa_user"),
    "password": os.getenv("DB_PASSWORD", "qa_password"),
}