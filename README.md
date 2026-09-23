# Pagila API Data Tests

A small TypeScript learning project that checks a REST API's responses against the underlying PostgreSQL data directly, using Playwright's API request testing. It runs on top of [Pagila](https://github.com/devrimgunduz/pagila), the standard PostgreSQL port of the "Sakila" DVD-rental sample database.

## What this project does

- Runs a minimal Express API backed by a Pagila PostgreSQL database.
- Exposes `GET /api/customer/:id`, returning a customer record as JSON.
- A Playwright test (`tests/api-customer.spec.ts`) calls that endpoint, then queries the same row directly from PostgreSQL, and asserts that the API response matches the database row (`first_name`, `last_name`, `email`).
- Runs automatically in CI (GitHub Actions) against a disposable Postgres 15 service container, seeded with the Pagila schema and data on every run.

## Tech stack

- TypeScript / Node.js
- Express — REST API server
- [pg](https://node-postgres.com/) — PostgreSQL client
- [@playwright/test](https://playwright.dev/) — API-level test runner and assertions
- GitHub Actions — CI pipeline
- PostgreSQL 15 (Pagila sample database)

## Project structure

```
src/
  server.ts               # Express app entry point; mounts the customer router,
                           # exposes GET /health/db
  routes/
    customer.ts            # GET /api/customer/:id
    health.ts               # standalone health-check router (not currently mounted in server.ts)
  controllers/
    customerController.ts   # customer-creation logic (not currently wired to a route)
  utils/
    db.ts                    # pg connection pool + logging query wrapper

scripts/
  seed.ts                    # inserts the one test customer row the test checks against
  pagila-schema.sql           # Pagila database schema
  pagila-data.sql             # Pagila sample data dump

tests/
  api-customer.spec.ts        # the API <-> database reconciliation test

.github/workflows/test.yml    # CI pipeline: starts Postgres, loads Pagila, starts the API, runs the tests
```

## Prerequisites

- Node.js 20+
- A running PostgreSQL instance loaded with the Pagila schema and data (`scripts/pagila-schema.sql`, `scripts/pagila-data.sql`)
- A `.env` file in the project root with a `DB_URL` connection string, e.g.

  ```
  DB_URL=postgres://<user>:<password>@localhost:5432/pagila
  ```

  Keep real credentials out of version control — use a local, non-production password and add `.env` to `.gitignore`.

## Running locally

1. Install dependencies:

   ```
   npm install
   ```

2. Load the Pagila schema and sample data into your Postgres database:

   ```
   psql -h localhost -U postgres -d pagila -f scripts/pagila-schema.sql
   psql -h localhost -U postgres -d pagila -f scripts/pagila-data.sql
   ```

3. Start the API server:

   ```
   npx ts-node src/server.ts
   ```

4. In a separate terminal, run the seed script:

   ```
   npx ts-node scripts/seed.ts
   ```

   Note: at this point `customer_id = 1` already exists from the Pagila sample data (as "MARY SMITH"), and `seed.ts` inserts with `ON CONFLICT (customer_id) DO NOTHING`, so this step currently has no effect in this order — see [Notes](#notes).

5. Run the tests:

   ```
   npx playwright test
   ```

## Continuous Integration

On every push and pull request to `main`, the GitHub Actions workflow (`.github/workflows/test.yml`):

1. Spins up a disposable PostgreSQL 15 service container.
2. Loads the Pagila schema and sample data.
3. Starts the Express API and waits for its `/health/db` check to report a successful database connection.
4. Seeds the one test customer row.
5. Runs the Playwright test suite against the live API and database.

## Notes

- There is currently one test: it verifies that `GET /api/customer/:id` returns data matching the corresponding row in the `customer` table. As currently seeded, this validates against Pagila's own sample row for `customer_id = 1` ("MARY SMITH"), not a custom fixture.
- `scripts/seed.ts` inserts a row for `customer_id = 1` using `ON CONFLICT (customer_id) DO NOTHING`. Since the Pagila sample data already contains a row with `customer_id = 1`, running `seed.ts` after loading `pagila-data.sql` — as both the local steps above and the CI workflow currently do — is a no-op: verified by running the sequence end-to-end, the customer record is unchanged before and after the seed step. To make the seed script take effect, it would need to run against an empty `customer` table, or use a customer ID that isn't already in the Pagila sample data, or use `ON CONFLICT ... DO UPDATE`.
- There is no `playwright.config.ts` in the repository; Playwright runs with its default configuration. This works here because the single test uses Playwright's `request` fixture for API/HTTP calls only — no browser is launched, so no browser install step is required.
- `src/controllers/customerController.ts` and `src/routes/health.ts` are present in the source tree but are not currently wired into `src/server.ts`.

## About

Personal learning/practice project exploring API-to-database data reconciliation testing with Playwright and TypeScript, run through a CI pipeline on GitHub Actions.
