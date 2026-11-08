# EquityIQ build log

This log records each completed coding step. Before stopping after a future step,
record its purpose, changed files, how the pieces connect, verification, and what
remains. Commands below run from `backend` unless stated otherwise.
Starting with Step 8, each completed step is also committed and pushed to the
project's GitHub `main` branch.

## Step 1 — FastAPI foundation

- **Purpose:** Start a small, runnable API.
- **Files:** `backend/app/main.py`, `backend/pyproject.toml`,
  `backend/tests/test_health.py`, root `README.md`, and `.gitignore`.
- **How it works:** FastAPI maps `GET /api/v1/health` to a function that returns
  `{"status": "ok"}`. Uvicorn runs the app; Pydantic defines the response shape.
- **Verification:** The health endpoint test passed (1 test).
- **Boundary:** The endpoint checked only that the API process could respond.

## Step 2 — Environment configuration

- **Purpose:** Move app settings out of `main.py`.
- **Files:** `backend/app/core/config.py`, root `.env.example`,
  `backend/tests/test_config.py`, and dependency updates in `pyproject.toml`.
- **How it works:** `Settings` reads defaults, optional root `.env` values, and
  `EQUITYIQ_` environment variables. `main.py` uses those settings at startup.
- **Verification:** An environment override changed the API title; 3 tests passed.
- **Boundary:** Changing `.env` requires restarting the API process.

## Step 3 — PostgreSQL connection check

- **Purpose:** Let the API report whether PostgreSQL can answer a query.
- **Files:** `backend/app/db/connection.py`, `backend/app/main.py`,
  `backend/tests/test_readiness.py`, `.env.example`, and `pyproject.toml`.
- **How it works:** The configured URL creates a lazy SQLAlchemy engine. Calling
  `GET /api/v1/ready` opens a connection and runs `SELECT 1`. It returns HTTP 200
  on success and HTTP 503 if the database is unavailable.
- **Verification:** Offline tests covered no configuration, a successful query,
  an invalid driver, and a connection failure; 7 tests passed in total.
- **Boundary:** Creating an engine does not create a database or any tables.

## Step 4 — Local PostgreSQL database

- **Purpose:** Connect the API to a real local server.
- **Files or state:** Created database `equityiq` and login `equityiq_app` on
  PostgreSQL 17 at `127.0.0.1:5432`. Stored the generated application password
  only in the Git ignored root `.env`. Updated `README.md`.
- **How it works:** The `.env` URL gives SQLAlchemy the host, port, login, and
  database. pgAdmin can inspect the same database as a separate client.
- **Verification:** `/api/v1/ready` returned HTTP 200. A live query reported
  `equityiq_app` as the user and `equityiq` as the database; 7 tests passed.
- **Boundary:** The database did not yet contain EquityIQ tables.

## Step 5 — Per-request database sessions

- **Purpose:** Prepare a session for each future database-backed API request.
- **Files:** `backend/app/db/session.py`, `backend/app/db/base.py`,
  `backend/app/main.py`, and `backend/tests/test_session.py`.
- **How it works:** A session factory is bound to the engine. FastAPI routes can
  request `get_db`, which supplies a session and closes it after the request.
  `Base` is the parent class for future ORM models.
- **Verification:** A session queried the live `equityiq` database. Offline
  tests checked successful use, missing configuration, and session closing;
  10 tests passed in total.
- **Boundary:** No production route used `get_db` yet. The dependency does not
  commit database writes automatically.

## Step 6 — First model and Alembic migration

- **Purpose:** Create a versioned schema change that can be seen in pgAdmin.
- **Files:** `backend/app/models/company.py`, `backend/alembic.ini`,
  `backend/alembic/env.py`,
  `backend/alembic/versions/20261106_0001_create_companies.py`, and
  `pyproject.toml` (Alembic dependency).
- **How it works:** `Company` maps Python objects to the `companies` table. The
  migration creates that table and a legal-name index. Alembic records the
  applied revision in `alembic_version`.
- **Verification:** `python -m alembic upgrade head` applied revision
  `20261106_0001`; `python -m alembic check` found no schema differences.
  PostgreSQL inspection found both tables. An ORM insert set an ID and timestamps,
  then was rolled back; 10 automated tests passed.
- **Boundary:** The `companies` table is empty. Tickers, exchanges, and company
  API routes have not been added.

## Step 7 — Exchange and security identity

- **Purpose:** Keep a company separate from each of its exchange listings.
- **Files:** `backend/app/models/exchange.py`, `backend/app/models/security.py`,
  `backend/app/models/__init__.py`, `backend/alembic/env.py`,
  `backend/alembic/versions/20261107_0002_add_exchanges_and_securities.py`,
  `backend/tests/test_listing_identity.py`, and `README.md`.
- **How it works:** An exchange has a unique code. A security links to one
  company and one exchange, and stores its symbol, optional ISIN, currency, and
  active status. The `(exchange_id, symbol)` pair is unique, so the same symbol
  can exist on different exchanges without silently choosing one listing.
- **Verification:** The offline test allowed matching symbols on two exchanges
  and rejected a duplicate on one exchange; 11 tests passed in total. Alembic
  applied revision `20261107_0002` and found no schema differences. A live ORM
  transaction inserted a company with two listings, then rolled back; no probe
  rows remain.
- **Boundary:** No exchange or security records have been saved, and no stock
  search or market-data API has been added.

## Step 8 — Market-data provider contract

- **Purpose:** Define one stable shape for market data before implementing a
  specific external provider.
- **Files:** `backend/app/services/market_data/provider.py`,
  `backend/app/services/market_data/schemas.py`,
  `backend/tests/test_market_data_contract.py`, and `README.md`.
- **How it works:** Every provider must implement search, exact-listing profile,
  and daily price methods. A `SecurityKey` includes exchange and symbol. Results
  include provenance and timezone-aware retrieval time. Price history declares
  its adjustment basis and an explicit reason when no data is available.
- **Verification:** Offline validation tests reject missing exchange identity,
  naive timestamps, invalid OHLCV data, and unexplained empty price history;
  15 tests passed in total.
- **Boundary:** There is no Yahoo adapter, network call, stock route, or saved
  market data yet.

## Step 9 — Yahoo Finance market-data adapter

- **Purpose:** Fetch Indian equity research data through the Step 8 contract.
- **Files:** `backend/app/services/market_data/yahoo.py`,
  `backend/tests/test_yahoo_provider.py`, `backend/pyproject.toml`, and `README.md`.
- **How it works:** `YahooMarketDataProvider` translates NSE/BSE listing keys to
  Yahoo symbols, searches equity listings, checks exact-listing profiles, and
  converts daily prices to validated OHLCV bars. It records source and retrieval
  time, requests dividend-adjusted prices, and distinguishes missing data from
  provider failures. It adds one day to the requested end date because Yahoo's
  end parameter is exclusive.
- **Verification:** Offline tests cover exchange identity, profile mismatch,
  missing listings, inclusive date handling, valid bars, invalid bars, and
  provider failure; 22 tests passed in total. Live personal-use checks found
  TCS on NSE and BSE, returned an NSE profile, and returned five daily bars for
  2–6 November 2026.
- **Boundary:** The adapter is not connected to an API route or PostgreSQL, and
  does not sync with INDmoney or generate investment recommendations. Yahoo
  data is for personal research under its terms of use.

## Step 10 — Read-only stock research routes

- **Purpose:** Make the Step 9 provider accessible in the API and interactive
  FastAPI documentation.
- **Files:** `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`,
  `backend/app/api/v1/stocks.py`, `backend/app/main.py`,
  `backend/tests/test_stock_routes.py`, and `README.md`.
- **How it works:** Search, exact-listing profile, and inclusive daily-price
  routes use a replaceable `MarketDataProvider` dependency. FastAPI validates
  exchanges, symbols, limits, and dates. Missing profiles return 404; invalid
  requests return 422; provider failures return a sanitized 502. Results keep
  their source and retrieval time.
- **Verification:** 26 automated tests passed. Offline route tests cover
  request validation, exchange identity, missing profiles, returned bars, and
  provider failures. OpenAPI listed all three routes, and a live HTTP search
  returned TCS listings on NSE and BSE.
- **Boundary:** The routes do not write market data to PostgreSQL, connect to
  INDmoney, place trades, or generate recommendations.
