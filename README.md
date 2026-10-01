# Pagila API — Data & Contract Tests

A small Express API over the [Pagila](https://github.com/devrimgunduz/pagila) sample database,
tested by **two independent suites written in different stacks**:

| Suite | Stack | Location |
| --- | --- | --- |
| Contract + data consistency | TypeScript, Playwright | [`tests/`](tests/) |
| JSON Schema + contract + data consistency | Python, PyTest, `jsonschema`, `psycopg2` | [`tests_python/`](tests_python/) |

Both hit the same endpoint on the same database, and both run in parallel on every push
via GitHub Actions. The point of keeping two is deliberate: the same behaviour described
twice, in two languages, is a useful way to show that the tests describe the *API* rather
than the *test framework*.

[![API Data Tests](https://github.com/teddorian/pagila-api-data-tests/actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)

## Tech stack

- **Runtime** — TypeScript / Node.js 20, Express, [pg](https://node-postgres.com/)
- **Tests** — [@playwright/test](https://playwright.dev/) (TypeScript) and
  [PyTest](https://docs.pytest.org/) with
  [`requests`](https://requests.readthedocs.io/),
  [`jsonschema`](https://python-jsonschema.readthedocs.io/) and
  [`psycopg2`](https://www.psycopg.org/) (Python 3.12)
- **Database** — PostgreSQL 15, loaded with the Pagila sample data
- **CI** — GitHub Actions, two parallel jobs against a disposable Postgres service container

---

## The API

| Method | Path | Response |
| --- | --- | --- |
| `GET` | `/health` | `{ "status": "ok" }` |
| `GET` | `/health/db` | `{ "status": "ok", "db": "connected" }`, or `500` with `"db": "unreachable"` |
| `GET` | `/api/customer/:id` | `{ customer_id, first_name, last_name, email }`, or `404` `{ "error": "Customer not found" }` |
| `POST` | `/api/customer` | `201` with the same four fields. Requires `first_name`, `last_name`, `store_id`, `address_id`; `email` is optional. `400` with `{ "error": ... }` on a missing field, a non-integer id, or an unknown `store_id`/`address_id`. |

```
src/
  server.ts                  Express app wiring
  routes/customer.ts         GET /api/customer/:id
  routes/health.ts           liveness + database readiness
  utils/db.ts                pg connection pool with query timing
  controllers/customerController.ts   POST /api/customer
scripts/
  pagila-schema.sql          Pagila DDL
  pagila-data.sql            Pagila fixture data
  seed.ts                    inserts the deterministic test customer
```

---

## Setup

Requires Node.js 20+, Python 3.12+ and a local PostgreSQL 15+.

```bash
git clone https://github.com/teddorian/pagila-api-data-tests.git
cd pagila-api-data-tests
npm install

cp .env.example .env          # then edit DB_URL to match your Postgres
```

Load the database:

```bash
createdb pagila
psql -d pagila -f scripts/pagila-schema.sql
psql -d pagila -f scripts/pagila-data.sql
npm run seed                  # see the note on seeding below
```

Start the API (leave it running in its own shell):

```bash
npm start                     # http://localhost:3000
```

---

## Running the tests

### TypeScript / Playwright

```bash
npm run test:ts
```

Checks that `GET /api/customer/1` returns the values that a direct `pg` query returns for
the same row.

### Python / PyTest

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm run test:py               # or: pytest
pytest -m schema              # only the JSON Schema checks
pytest -m contract            # only status codes and error payloads
pytest -m data                # only API-vs-database consistency
pytest --base-url http://localhost:3000
```

59 tests across three markers, split into
[`test_api_customer.py`](tests_python/test_api_customer.py) (reads),
[`test_api_customer_create.py`](tests_python/test_api_customer_create.py) (writes) and
[`test_customer_integrity.py`](tests_python/test_customer_integrity.py) (database integrity):

- **`schema`** — the response body is validated against a strict JSON Schema
  (`tests_python/schemas/customer.schema.json`, draft 2020-12): field types, required
  fields, `format: email`, `maxLength` taken from the classic Sakila column widths (the Pagila columns themselves are unbounded `text`, which is why the API must enforce them), and
  `additionalProperties: false` so that a newly added database column cannot silently
  leak into the public response. The same schema is applied to the `201` body of
  `POST /api/customer`, which is how the two endpoints are held to one contract. A
  separate test asserts that no internal column (`address_id`, `store_id`, `activebool`,
  …) appears in either payload.
- **`contract`** — `404` for an unknown id with the error body validated against its own
  schema, rejection of malformed ids (`abc`, `1.5`, `-1`, whitespace, an injection-shaped
  string), a `400` for each individually omitted required field on `POST`, non-integer
  and out-of-range ids, a foreign key violation surfacing as `400` rather than `500`, and
  the health endpoints.
- **`data`** — the API response is compared field by field against a direct `psycopg2`
  query, so a serialisation bug in the route cannot pass unnoticed. Newly created
  customers are read back both from the database and through `GET`, and every row a test
  inserts is removed in teardown, so the suite is repeatable against a long-lived
  database. A created customer is joined back to `address` and `store` to prove the
  relations were stored as requested, and a single `POST` must insert exactly one row.
  Boundary values (names of 1 and 45 characters, including multibyte, and a 50-character
  email) must round-trip unchanged.
- **Integrity** (also under `data`) — read straight from the database: the column types
  and nullability in `information_schema` match the JSON contract, the `address_id` and
  `store_id` foreign keys exist, and there are no orphaned customers and no duplicate
  emails.

See [`tests_python/README.md`](tests_python/README.md) for details.

### Type checking

```bash
npm run typecheck
```

---

## Known defects, documented by tests

Each defect below is captured by a test marked `xfail(strict=True)`: it is expected to fail
today, and it will turn into a *failure* the moment the API is fixed, at which point the
marker should be removed. The bugs are described by tests rather than by comments, so they
cannot quietly disappear.

| Defect | Test |
| --- | --- |
| `GET /api/customer/abc` answers **500**, not **400**: a non-numeric id is passed straight to PostgreSQL. | `test_malformed_id_should_return_400` |
| A repeated `POST` with the same email (in any letter case) creates a duplicate customer: there is no unique constraint and no check in the route. | `test_repeated_post_with_same_email_is_rejected` |
| An empty name or a name of 46+ characters is accepted, stored, and returned in breach of the schema's `minLength: 1` / `maxLength: 45`. The columns are unbounded `text` and the route only checks that the field is present. | `test_name_outside_the_boundary_returns_400` |
| An email of 51+ characters is accepted, in breach of the schema's `maxLength: 50`. | `test_email_over_max_length_returns_400` |

---

## CI

[`.github/workflows/test.yml`](.github/workflows/test.yml) runs two jobs in parallel on
every push and pull request to `main`. Each job stands up a PostgreSQL 15 service
container, loads the Pagila schema and data, seeds the test customer, starts the API, and
then runs its own suite. The PyTest job also uploads a JUnit XML report as a build
artifact.

---

## Notes

- **`scripts/seed.ts` is currently a no-op in the documented order.** It inserts a row for
  `customer_id = 1` with `ON CONFLICT (customer_id) DO NOTHING`, but `pagila-data.sql`
  already contains that id (Pagila's own "MARY SMITH"), so nothing is written — both the
  local steps above and the CI workflow load the sample data first. The tests therefore
  assert against Pagila's sample row rather than a custom fixture, which is fine for a
  reconciliation test but worth knowing. Making the seed take effect would mean running it
  against an empty `customer` table, choosing an id outside the sample data, or switching
  to `ON CONFLICT ... DO UPDATE`.
- `.env` is not committed; copy `.env.example` and fill in your own connection string.
- `DB_URL` is read from the environment by both the server and both test suites.
- `API_BASE_URL` overrides the target host for both suites (defaults to
  `http://localhost:3000`).

---

## About

A practice project exploring API-to-database reconciliation testing: the same contract
described twice, in two stacks, and enforced on every push by CI.
