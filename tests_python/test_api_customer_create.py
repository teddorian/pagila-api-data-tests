"""API tests for POST /api/customer.

Every test that creates a row registers its id with the `cleanup_customers`
fixture, so the suite is repeatable against a long-lived database.
"""

import uuid

import pytest

CUSTOMER_SQL = (
    "SELECT customer_id, first_name, last_name, email "
    "FROM customer WHERE customer_id = %s"
)

REQUIRED_FIELDS = ["first_name", "last_name", "store_id", "address_id"]

# Limits published in customer.schema.json; the API must not create a row it
# could then only return in breach of its own contract.
NAME_MAX = 45
EMAIL_MAX = 50
EMAIL_DOMAIN = "@example.com"


def unique_email(length=None):
    """An address no other row uses, optionally padded to an exact length."""
    local = f"pytest.{uuid.uuid4().hex}"
    if length is not None:
        local = local[: length - len(EMAIL_DOMAIN)].ljust(length - len(EMAIL_DOMAIN), "x")
    return local + EMAIL_DOMAIN


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


@pytest.mark.data
def test_created_customer_references_the_requested_store_and_address(create, db_row, valid_payload):
    # Use the highest ids rather than the first customer's, so a route that
    # ignored the payload and fell back to a default could not pass.
    related = db_row(
        "SELECT (SELECT MAX(store_id) FROM store) AS store_id, "
        "(SELECT MAX(address_id) FROM address) AS address_id",
        (),
    )
    valid_payload.update(related)

    body = create(valid_payload).json()

    stored = db_row(
        """
        SELECT c.store_id, c.address_id, a.address, s.store_id AS joined_store_id
        FROM customer c
        JOIN address a ON a.address_id = c.address_id
        JOIN store s ON s.store_id = c.store_id
        WHERE c.customer_id = %s
        """,
        (body["customer_id"],),
    )
    assert stored is not None, "the created customer does not join to its address and store"
    assert stored["store_id"] == related["store_id"]
    assert stored["address_id"] == related["address_id"]
    assert stored["joined_store_id"] == related["store_id"]


@pytest.mark.contract
def test_unknown_store_id_returns_400_not_500(create, valid_payload, db_row):
    valid_payload["store_id"] = db_row("SELECT MAX(store_id) + 1 AS id FROM store", ())["id"]

    response = create(valid_payload)

    assert response.status_code == 400, "a foreign key violation must not surface as a 500"
    assert "store_id" in response.json()["error"]


@pytest.mark.data
def test_one_post_inserts_exactly_one_row(create, db_row, valid_payload):
    valid_payload["email"] = unique_email()

    create(valid_payload)

    count = db_row("SELECT COUNT(*) AS n FROM customer WHERE email = %s", (valid_payload["email"],))
    assert count["n"] == 1


@pytest.mark.contract
@pytest.mark.xfail(
    strict=True,
    reason="Known defect: customer.email has no unique constraint and the route does not "
    "check for an existing customer, so a repeated POST creates a duplicate.",
)
def test_repeated_post_with_same_email_is_rejected(create, db_row, valid_payload):
    valid_payload["email"] = unique_email()
    assert create(valid_payload).status_code == 201

    repeated = create(dict(valid_payload, email=valid_payload["email"].upper()))

    count = db_row(
        "SELECT COUNT(*) AS n FROM customer WHERE lower(email) = lower(%s)",
        (valid_payload["email"],),
    )
    assert repeated.status_code in (400, 409), f"duplicate accepted with {repeated.status_code}"
    assert count["n"] == 1


@pytest.mark.data
@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize(
    "value",
    ["A", "A" * NAME_MAX, "Ж" * NAME_MAX],
    ids=["min-length", "max-length", "max-length-multibyte"],
)
def test_name_at_the_boundary_is_stored_exactly(create, db_row, assert_valid, valid_payload, field, value):
    valid_payload[field] = value

    response = create(valid_payload)

    assert response.status_code == 201
    assert_valid(response.json(), "customer.schema.json")
    stored = db_row(CUSTOMER_SQL, (response.json()["customer_id"],))
    assert stored[field] == value


@pytest.mark.contract
@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize(
    "value",
    ["", "A" * (NAME_MAX + 1)],
    ids=["empty", "one-over-max"],
)
@pytest.mark.xfail(
    strict=True,
    reason="Known defect: the route only checks that names are present, and the columns are "
    "unbounded text, so names outside 1..45 are stored and returned in breach of the schema.",
)
def test_name_outside_the_boundary_returns_400(create, valid_payload, field, value):
    valid_payload[field] = value

    response = create(valid_payload)

    assert response.status_code == 400, f"{field} of length {len(value)} was accepted"


@pytest.mark.data
def test_email_at_max_length_is_stored_exactly(create, db_row, assert_valid, valid_payload):
    valid_payload["email"] = unique_email(EMAIL_MAX)

    response = create(valid_payload)

    assert response.status_code == 201
    assert_valid(response.json(), "customer.schema.json")
    assert db_row(CUSTOMER_SQL, (response.json()["customer_id"],))["email"] == valid_payload["email"]


@pytest.mark.contract
@pytest.mark.xfail(
    strict=True,
    reason="Known defect: email length is not validated, so an address over 50 characters "
    "is stored and returned in breach of the schema.",
)
def test_email_over_max_length_returns_400(create, valid_payload):
    valid_payload["email"] = unique_email(EMAIL_MAX + 1)

    response = create(valid_payload)

    assert response.status_code == 400, "an email over the maximum length was accepted"
