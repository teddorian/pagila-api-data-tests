# Python / PyTest API tests

A second, independent test suite over the same Pagila API that `tests/api-customer.spec.ts`
covers with TypeScript/Playwright. Same server, same database, different stack — the two
suites are meant to be read side by side.

- `test_api_customer.py` — reads: `GET /api/customer/:id` and the health endpoints.
- `test_api_customer_create.py` — writes: `POST /api/customer`.
- `test_customer_integrity.py` — database integrity: column types vs. the contract, foreign keys, orphans, duplicate emails.

## What it checks

| Marker | Focus |
| --- | --- |
| `schema` | The JSON body of `GET /api/customer/:id` **and** the `201` body of `POST /api/customer` validate against one strict JSON Schema (`schemas/customer.schema.json`): field types, required fields, `format: email`, `maxLength` taken from the classic Sakila column widths (the Pagila columns themselves are unbounded `text`, which is why the API must enforce them), and `additionalProperties: false` so a new column cannot silently leak into the API. |
| `contract` | Status codes and error payloads: `404` for an unknown id (validated against `schemas/error.schema.json`), rejection of malformed ids, a `400` per individually omitted required field on `POST`, non-integer and out-of-range ids, a foreign key violation returning `400` instead of `500`, and the health endpoints. |
| `data` | The values the API returns are exactly the values stored in Postgres — the API response is compared against a direct `psycopg2` query. Created customers are read back both from the database and through `GET`, joined to `address` and `store`, and boundary-length values must round-trip unchanged. The integrity file adds column types vs. the contract, foreign keys, orphans and duplicate emails. Known defects (duplicates, unbounded name and email length) are pinned as `xfail(strict=True)`. |

## Writes and cleanup

`POST` tests insert real rows. Each one registers the created `customer_id` with the
`cleanup_customers` fixture, which deletes them in teardown over a separate writable
connection — the connection used for assertions is opened `readonly=True` so a test
cannot accidentally mutate the data it is checking. Running the suite twice in a row
leaves the row count unchanged.

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# in another shell: start the API
npx ts-node src/server.ts

pytest                      # everything
pytest -m schema            # only the JSON Schema checks
pytest --base-url http://localhost:3000
```

`DB_URL` is read from `.env` (or the environment). `--base-url` defaults to
`$API_BASE_URL`, then `http://localhost:3000`.

## Known defect documented by the suite

`test_malformed_id_should_return_400` is a `strict=True` xfail: a non-numeric id such as
`/api/customer/abc` is passed straight to Postgres, so the client gets `500` where `400`
is the correct answer. The test will start failing — loudly — the moment the route is
fixed, at which point the `xfail` marker should be removed.
