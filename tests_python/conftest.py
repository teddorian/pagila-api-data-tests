"""Shared fixtures: HTTP session, database connection and JSON Schema loading."""

import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
import requests
from dotenv import load_dotenv
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).parent / "schemas"

load_dotenv()


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=os.getenv("API_BASE_URL", "http://localhost:3000"),
        help="Base URL of the running API server",
    )


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    return pytestconfig.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.getenv("DB_URL")
    if not url:
        pytest.fail("DB_URL is not set (put it in .env or export it before running pytest)")
    return url


@pytest.fixture(scope="session")
def db(db_url):
    """One read-only connection reused by the whole session."""
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def db_write(db_url):
    """A writable connection, kept apart from the read-only one used for assertions."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture
def db_row(db):
    """Fetch a single row as a dict, or None."""

    def _fetch(sql: str, params: tuple):
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return dict(row) if row is not None else None

    return _fetch


@pytest.fixture(scope="session")
def api(base_url):
    """HTTP session that resolves relative paths against the API base URL."""

    class ApiClient:
        def __init__(self):
            self._session = requests.Session()

        def get(self, path: str, **kwargs) -> requests.Response:
            kwargs.setdefault("timeout", 10)
            return self._session.get(f"{base_url}{path}", **kwargs)

        def post(self, path: str, **kwargs) -> requests.Response:
            kwargs.setdefault("timeout", 10)
            return self._session.post(f"{base_url}{path}", **kwargs)

        def close(self):
            self._session.close()

    client = ApiClient()
    yield client
    client.close()


@pytest.fixture(scope="session", autouse=True)
def api_is_up(api):
    """Fail fast with a readable message instead of a connection error per test."""
    try:
        response = api.get("/health/db")
    except requests.exceptions.ConnectionError:
        pytest.fail(
            "API is not reachable. Start it first: npx ts-node src/server.ts"
        )
    assert response.status_code == 200, f"/health/db returned {response.status_code}"
    assert response.json().get("db") == "connected"


@pytest.fixture(scope="session")
def schema():
    """Load a JSON Schema by file name and return a validator with format checking on."""
    cache: dict[str, Draft202012Validator] = {}

    def _load(name: str) -> Draft202012Validator:
        if name not in cache:
            with open(SCHEMA_DIR / name, encoding="utf-8") as fh:
                document = json.load(fh)
            Draft202012Validator.check_schema(document)
            cache[name] = Draft202012Validator(document, format_checker=FormatChecker())
        return cache[name]

    return _load


@pytest.fixture
def assert_valid(schema):
    """Validate a payload and report every violation at once, not just the first."""

    def _assert(payload, schema_name: str):
        validator = schema(schema_name)
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            details = "\n".join(
                f"  - {'/'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
                for error in errors
            )
            pytest.fail(f"Payload does not match {schema_name}:\n{details}")

    return _assert


@pytest.fixture
def cleanup_customers(db_write):
    """Register customer ids created by a test; delete them once it finishes."""
    created: list[int] = []

    yield created

    if created:
        with db_write.cursor() as cur:
            cur.execute("DELETE FROM customer WHERE customer_id = ANY(%s)", (created,))
