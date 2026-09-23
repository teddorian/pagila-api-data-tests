"""API tests for POST /api/customer.

Every test that creates a row registers its id with the `cleanup_customers`
fixture, so the suite is repeatable against a long-lived database.
"""

import pytest

CUSTOMER_SQL = (
    "SELECT customer_id, first_name, last_name, email "
    "FROM customer WHERE customer_id = %s"
)

REQUIRED_FIELDS = ["first_name", "last_name", "store_id", "address_id"]


@pytest.fixture
def valid_payload(db_row):
    """A payload whose store_id and address_id really exist, so the FK holds."""
    reference = db_row(
        "SELECT store_id, address_id FROM customer ORDER BY customer_id LIMIT 1", ()
    )
    if reference is None:
        pytest.fail("The customer table is empty - load the Pagila data first")

    return {
        "first_name": "Pytest",
        "last_name": "Fixture",
        "email": "pytest.fixture@example.com",
        "store_id": reference["store_id"],
        "address_id": reference["address_id"],
    }


@pytest.fixture
def create(api, cleanup_customers):
    """POST a payload and remember the created id for teardown."""

    def _create(payload):
        response = api.post("/api/customer", json=payload)
        if response.status_code == 201:
            cleanup_customers.append(response.json()["customer_id"])
        return response

    return _create


@pytest.mark.schema
def test_created_customer_matches_json_schema(create, assert_valid, valid_payload):
    response = create(valid_payload)

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/json")
    assert_valid(response.json(), "customer.schema.json")


@pytest.mark.schema
def test_create_response_does_not_leak_private_columns(create, valid_payload):
    payload = create(valid_payload).json()

    assert set(payload) == {"customer_id", "first_name", "last_name", "email"}


@pytest.mark.data
def test_created_customer_is_persisted(create, db_row, valid_payload):
    body = create(valid_payload).json()

    stored = db_row(CUSTOMER_SQL, (body["customer_id"],))
    assert stored == body


@pytest.mark.data
def test_created_customer_is_readable_through_get(api, create, assert_valid, valid_payload):
    created = create(valid_payload).json()

    response = api.get(f"/api/customer/{created['customer_id']}")

    assert response.status_code == 200
    assert_valid(response.json(), "customer.schema.json")
    assert response.json() == created


@pytest.mark.data
def test_email_may_be_omitted(create, db_row, valid_payload):
    valid_payload.pop("email")

    response = create(valid_payload)

    assert response.status_code == 201
    assert response.json()["email"] is None
    assert db_row(CUSTOMER_SQL, (response.json()["customer_id"],))["email"] is None


@pytest.mark.contract
@pytest.mark.parametrize("omitted", REQUIRED_FIELDS)
def test_missing_required_field_returns_400(create, assert_valid, valid_payload, omitted):
    valid_payload.pop(omitted)

    response = create(valid_payload)

    assert response.status_code == 400, f"omitting {omitted!r} was accepted"
    assert_valid(response.json(), "error.schema.json")
    assert omitted in response.json()["error"]


@pytest.mark.contract
def test_empty_payload_reports_every_missing_field(create, valid_payload):
    response = create({})

    assert response.status_code == 400
    message = response.json()["error"]
    for field in REQUIRED_FIELDS:
        assert field in message, f"{field!r} is not mentioned in {message!r}"


@pytest.mark.contract
@pytest.mark.parametrize("bad_value", ["not-a-number", 0, -5, 1.5, True])
def test_non_integer_address_id_returns_400(create, valid_payload, bad_value):
    valid_payload["address_id"] = bad_value

    response = create(valid_payload)

    assert response.status_code == 400, f"address_id={bad_value!r} was accepted"


@pytest.mark.contract
def test_unknown_address_id_returns_400_not_500(create, valid_payload, db_row):
    orphan = db_row("SELECT MAX(address_id) + 1000 AS id FROM address", ())["id"]
    valid_payload["address_id"] = orphan

    response = create(valid_payload)

    assert response.status_code == 400, "a foreign key violation must not surface as a 500"
    assert "address_id" in response.json()["error"]


@pytest.mark.contract
def test_creating_a_customer_does_not_change_the_row_count_after_cleanup(
    api, db_row, valid_payload, cleanup_customers
):
    before = db_row("SELECT COUNT(*) AS n FROM customer", ())["n"]

    response = api.post("/api/customer", json=valid_payload)
    cleanup_customers.append(response.json()["customer_id"])

    after = db_row("SELECT COUNT(*) AS n FROM customer", ())["n"]
    assert after == before + 1
