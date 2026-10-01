"""Database-level integrity of the customer table behind the API.

These tests read the database directly: they check that the column types match
the published JSON contract, that the foreign keys the API relies on are really
enforced, and that the table holds no orphaned or duplicated customers.
"""

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent / "schemas" / "customer.schema.json"

# JSON Schema type -> PostgreSQL data types that serialise to it.
JSON_TO_PG_TYPES = {
    "integer": {"smallint", "integer", "bigint"},
    "string": {"text", "character varying", "character"},
}


@pytest.fixture
def db_rows(db):
    """Fetch every row as a tuple."""

    def _fetch(sql: str, params: tuple = ()):
        with db.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    return _fetch


def _contract_fields():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        properties = json.load(fh)["properties"]
    for name, spec in properties.items():
        types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
        yield name, [t for t in types if t != "null"][0], "null" in types


@pytest.mark.data
@pytest.mark.parametrize("column, json_type, nullable", list(_contract_fields()))
def test_column_type_matches_contract(db_row, column, json_type, nullable):
    info = db_row(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'customer' AND column_name = %s",
        (column,),
    )

    assert info is not None, f"customer.{column} is in the contract but not in the table"
    assert info["data_type"] in JSON_TO_PG_TYPES[json_type], (
        f"customer.{column} is {info['data_type']}, which does not serialise to {json_type}"
    )
    assert (info["is_nullable"] == "YES") == nullable, (
        f"customer.{column} nullability differs from the contract"
    )


@pytest.mark.data
@pytest.mark.parametrize(
    "column, referenced_table",
    [("address_id", "address"), ("store_id", "store")],
)
def test_foreign_key_is_enforced(db_row, column, referenced_table):
    fk = db_row(
        """
        SELECT ref.relname AS referenced_table
        FROM pg_constraint con
        JOIN pg_class ref ON ref.oid = con.confrelid
        JOIN pg_attribute att
          ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
        WHERE con.contype = 'f'
          AND con.conrelid = 'public.customer'::regclass
          AND att.attname = %s
        """,
        (column,),
    )

    assert fk is not None, f"customer.{column} has no foreign key - orphans would go unnoticed"
    assert fk["referenced_table"] == referenced_table


@pytest.mark.data
@pytest.mark.parametrize(
    "column, referenced_table",
    [("address_id", "address"), ("store_id", "store")],
)
def test_no_orphaned_customers(db_rows, column, referenced_table):
    # Identifiers come from the parametrize list above, never from input.
    orphans = db_rows(
        f"SELECT c.customer_id, c.{column} FROM customer c "
        f"LEFT JOIN {referenced_table} r ON r.{column} = c.{column} "
        f"WHERE r.{column} IS NULL ORDER BY c.customer_id LIMIT 10"
    )

    assert orphans == [], f"customers pointing at a missing {referenced_table}: {orphans}"


@pytest.mark.data
def test_no_duplicate_emails(db_rows):
    duplicates = db_rows(
        "SELECT lower(email), COUNT(*) FROM customer "
        "WHERE email IS NOT NULL GROUP BY lower(email) HAVING COUNT(*) > 1 LIMIT 10"
    )

    assert duplicates == [], f"emails shared by several customers: {duplicates}"
