"""API tests for GET /api/customer/:id.

Three layers of checks, each with its own marker:
  schema   - the response validates against tests_python/schemas/*.json
  contract - status codes and error payloads behave as documented
  data     - the values the API returns are the values stored in Postgres
"""

import pytest

CUSTOMER_SQL = (
    "SELECT customer_id, first_name, last_name, email "
    "FROM customer WHERE customer_id = %s"
)

# Columns the API must never leak, even though they live on the same table.
PRIVATE_COLUMNS = {"address_id", "store_id", "active", "activebool", "last_update"}


@pytest.fixture
def existing_customer(db_row):
    """A customer that is guaranteed to be present (seeded by scripts/seed.ts)."""
    row = db_row(CUSTOMER_SQL, (1,))
    if row is None:
        pytest.fail("Customer 1 is missing - run `ts-node scripts/seed.ts` first")
    return row


@pytest.mark.schema
def test_customer_response_matches_json_schema(api, assert_valid, existing_customer):
    response = api.get(f"/api/customer/{existing_customer['customer_id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert_valid(response.json(), "customer.schema.json")


@pytest.mark.schema
@pytest.mark.parametrize("customer_id", [1, 2, 3, 100, 599])
def test_schema_holds_for_multiple_customers(api, assert_valid, db_row, customer_id):
    if db_row(CUSTOMER_SQL, (customer_id,)) is None:
        pytest.skip(f"customer_id={customer_id} is not present in this database")

    response = api.get(f"/api/customer/{customer_id}")

    assert response.status_code == 200
    assert_valid(response.json(), "customer.schema.json")


@pytest.mark.schema
def test_response_does_not_leak_private_columns(api, existing_customer):
    payload = api.get(f"/api/customer/{existing_customer['customer_id']}").json()

    leaked = PRIVATE_COLUMNS & set(payload)
    assert not leaked, f"API exposed internal columns: {sorted(leaked)}"


@pytest.mark.data
def test_api_values_match_database(api, existing_customer):
    payload = api.get(f"/api/customer/{existing_customer['customer_id']}").json()

    assert payload == existing_customer


@pytest.mark.data
def test_customer_id_echoes_the_requested_id(api, existing_customer):
    requested = existing_customer["customer_id"]

    payload = api.get(f"/api/customer/{requested}").json()

    assert payload["customer_id"] == requested


@pytest.mark.contract
def test_unknown_customer_returns_404(api, assert_valid, db_row):
    missing_id = 999999
    assert db_row(CUSTOMER_SQL, (missing_id,)) is None, "pick an id that really is absent"

    response = api.get(f"/api/customer/{missing_id}")

    assert response.status_code == 404
    assert_valid(response.json(), "error.schema.json")


@pytest.mark.contract
@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", " ", "1%20OR%201=1"])
def test_malformed_id_is_rejected(api, bad_id):
    response = api.get(f"/api/customer/{bad_id}")

    assert response.status_code >= 400, (
        f"id={bad_id!r} was accepted with {response.status_code}"
    )
    assert "error" in response.json()


@pytest.mark.contract
def test_health_endpoint_reports_database_connection(api):
    response = api.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "connected"}


@pytest.mark.contract
@pytest.mark.xfail(
    strict=True,
    reason="Known defect: a non-numeric id reaches Postgres and surfaces as 500; "
           "the route should reject it with 400 before querying",
)
def test_malformed_id_should_return_400(api):
    assert api.get("/api/customer/abc").status_code == 400
