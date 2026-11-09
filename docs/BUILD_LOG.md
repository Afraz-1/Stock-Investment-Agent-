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

## Step 11 — Daily price storage schema

- **Purpose:** Prepare PostgreSQL to store provider price history per exact
  exchange listing.
- **Files:** `backend/app/models/daily_price.py`, `backend/app/models/__init__.py`,
  `backend/alembic/versions/20261108_0003_add_daily_prices.py`,
  `backend/tests/test_daily_price.py`, and `README.md`.
- **How it works:** `DailyPrice` links to `Security` and stores trading day,
  OHLCV, currency, provider, adjustment basis, source retrieval time, and an
  optional source URL. A unique key separates providers and adjustment types.
  Database checks reject invalid prices, negative volume, and unknown
  adjustment types. The foreign key prevents orphan price rows.
- **Verification:** 32 automated tests passed. Migration `20261108_0003` was
  applied to local PostgreSQL; `alembic check` found no schema differences.
  A live ORM insert received a generated ID, then was rolled back. The table
  has no saved price rows.
- **Boundary:** No ingestion service writes Yahoo results into this table yet.
  Existing stock routes still read the provider directly.

## Step 12 — Daily price ingestion service

- **Purpose:** Connect the market-data provider to the daily price table for
  securities already registered in PostgreSQL.
- **Files:** `backend/app/services/market_data/ingestion.py`,
  `backend/app/models/daily_price.py`, `backend/tests/test_price_ingestion.py`,
  and `README.md`.
- **How it works:** `ingest_daily_prices` loads the exact `Security` and
  `Exchange`, fetches an inclusive date range, checks listing identity,
  currency, and dates, then upserts the bars. Repeat fetches update existing
  rows, while an older retrieval cannot replace a newer one. It leaves commit
  or rollback to the caller.
- **Verification:** 39 automated tests passed. Offline tests cover initial
  storage, idempotent refresh, stale results, mismatched data, missing listings,
  provider failure, and rollback. A live PostgreSQL transaction fetched and
  stored five Yahoo TCS bars for 2–6 November 2026, then was rolled back.
- **Boundary:** No route, scheduler, or stock-registration flow calls this
  service yet. The local database has no persisted company, exchange,
  security, or price rows from verification.

## Step 13 — Local stock registration

- **Purpose:** Create a verified company and exchange listing so the Step 12
  price ingestion service has a real security ID to use.
- **Files:** `backend/app/services/market_data/registration.py`,
  `backend/app/cli/__init__.py`, `backend/app/cli/register_stock.py`,
  `backend/app/models/company.py`, `backend/app/models/exchange.py`,
  `backend/app/models/security.py`, `backend/tests/test_registration.py`,
  and `README.md`.
- **How it works:** A local command accepts NSE/BSE, a symbol, and either a
  verified legal name for a new company or an existing company ID for another
  listing. The service creates or reuses the exchange and listing, checks
  conflicting identity details, and leaves commit to the caller. The CLI
  commits on success. SQLite-only ID variants support offline tests without
  changing PostgreSQL's BIGINT schema.
- **Verification:** 47 automated tests passed; `alembic check` found no schema
  differences. The command registered TCS on NSE using name and ISIN checked
  against NSE's public listing. Repeating it returned the same company ID `5`
  and security ID `5`. PostgreSQL has one company, exchange, and security row,
  and zero price rows.
- **Boundary:** Registration is available only from the local terminal. It
  does not fetch or save prices, represent a holding, or recommend a stock.

## Step 14 — Local daily price import command

- **Purpose:** Make the Step 12 ingestion service usable for a registered
  stock without adding a public database-write endpoint.
- **Files:** `backend/app/cli/ingest_prices.py`,
  `backend/tests/test_ingest_prices_cli.py`, and `README.md`.
- **How it works:** The command accepts an NSE/BSE symbol and inclusive date
  range, resolves the registered security ID, calls the Yahoo provider through
  `ingest_daily_prices`, and commits the transaction. Invalid input, missing
  listings, provider failure, and database failure produce a nonzero exit.
- **Verification:** 52 automated tests passed. Offline CLI tests cover commit,
  repeat import without duplicates, invalid dates, missing listings, and
  provider failure. The live command imported TCS NSE prices for 2–6 November
  2026, then ran again; PostgreSQL retained exactly five rows. No schema
  migration was needed.
- **Boundary:** The command is local and manual. API routes still read Yahoo
  directly; there is no scheduler, recommendation, or trade execution.

## Step 15 — Local React stock explorer and saved-price view

- **Purpose:** Make the backend useful through a local website and show the
  difference between prices fetched from Yahoo and prices stored in PostgreSQL.
- **Files:** `frontend/` (React, TypeScript, Vite, Recharts, Lucide icons),
  `backend/app/api/v1/stocks.py`,
  `backend/app/services/market_data/schemas.py`,
  `backend/tests/test_saved_price_routes.py`, and `README.md`.
- **How it works:** Vite forwards `/api` requests to FastAPI during local
  development. The page searches NSE/BSE listings, shows a company profile,
  charts daily closing prices over 1M/3M/1Y, and switches between live Yahoo
  data and saved database rows. The new read-only `saved-prices` endpoint looks
  up one exact exchange/symbol listing and returns its Yahoo,
  dividend-adjusted bars for an inclusive range, plus retrieval timestamps.
  Missing registration returns 404; an empty range returns `no_data`.
- **Verification:** 55 backend tests passed, frontend lint and production
  build passed. Local HTTP checks returned the page, database readiness,
  Yahoo profile and prices, and five saved TCS bars for 2–6 November 2026.
  A visual browser preview was unavailable in this environment.
- **Boundary:** This is a personal local research interface. Saved bars still
  require the manual import command. It does not predict returns, recommend
  trades, access INDmoney, or support public users yet.

## Step 16 — My stocks and on-demand price saving

- **Purpose:** Add more listings from the website and save a selected range of
  historical prices without using the registration and import commands.
- **Files:** `backend/app/models/watchlist_item.py`, Alembic revision
  `20261109_0004`, `backend/app/api/v1/watchlist.py`, route registration in
  `backend/app/main.py`, `backend/tests/test_watchlist_routes.py`,
  `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/App.css`, and
  the README files.
- **How it works:** A watchlist row points to a registered security. The add
  route verifies the exact listing with the provider, then reuses the existing
  registration service and saves watchlist membership. The user checks the
  legal company name and optional ISIN before submitting. The refresh route uses the existing
  ingestion service and commits at most 366 days of Yahoo price bars. Repeat
  refreshes upsert instead of duplicating daily rows. Removing a watchlist row
  retains the underlying company, listing, and saved history. The migration
  backfills existing registered listings into the watchlist.
- **Verification:** 58 backend tests passed; the new offline API tests cover
  add, repeat add, exchange identity, refresh, idempotency, removal, retained
  prices, invalid input, and provider failure. The React build, lint, and
  formatting checks passed. Alembic reached `20261109_0004` with no schema
  drift. A live local request showed NSE:TCS in the watchlist with five saved
  days; refreshing one day received one bar and still left five saved rows.
- **Boundary:** These write routes are only for the loopback-hosted personal
  app. Authentication and request protection are required before public
  deployment. No automatic schedule, trade execution, or investment signal
  was added.

## Step 17 — Market movers and frontend design refresh

- **Purpose:** Add a useful top-stocks discovery view and bring the visual
  hierarchy closer to the supplied dark editorial and clean stock-list
  references.
- **Files:** `backend/app/services/market_data/movers.py`,
  `backend/app/api/v1/market.py`, `backend/tests/test_market_movers.py`,
  `backend/app/main.py`, `frontend/src/MarketOverview.tsx`,
  `frontend/src/MarketOverview.css`, `frontend/src/theme.css`, and updates to
  the existing frontend, `frontend/src/PriceChart.tsx`, README files, and this log.
- **How it works:** A read-only Yahoo screener requests the leading positive
  and negative daily moves among NSE equities with market cap of at least
  ₹10,000 crore and day volume of at least 100,000 shares. The service rejects
  incomplete or non-NSE quotes, keeps one latest trading date, sorts the
  returned moves, and caches results for five minutes. The frontend displays
  five gainers and five losers with price, percentage change, timestamp,
  source, universe criteria, and a click-through to stock research. The page
  gains a dark hero, more deliberate typography, and responsive list styling.
  The chart loads as a separate JavaScript chunk after the main interface.
- **Verification:** 61 backend tests passed. Offline mover tests check
  filtering, sorting, stale dates, caching, empty data, and upstream failure.
  The frontend build and lint passed. A live local request for 9 November
  2026 returned five gainers and five losers; the website returned HTTP 200.
  A browser preview surface was unavailable for visual inspection.
- **Boundary:** These are Yahoo-sourced daily price movers within a declared
  screen, not all NSE stocks or investment recommendations. Quotes may lag.
  Yahoo's personal-use data source is not a public distribution plan.

## Step 18 — Separate pages and top navigation

- **Purpose:** Make Market overview, Stock research, and My stocks distinct
  pages, with Market overview opening first and navigation across the top.
- **Files:** `frontend/src/main.tsx`, `frontend/src/App.tsx`,
  `frontend/src/StockSearch.tsx`, `frontend/src/navigation.css`,
  `frontend/scripts/check-routes.mjs`, `frontend/package.json`, package lock,
  and `frontend/README.md`.
- **How it works:** React Router reads the browser URL and renders one view:
  `/` for market movers, `/research` for the company chart and profile, and
  `/my-stocks` for the personal list and price saving. The sidebar is gone.
  Top links show the active page; the search component is shared by research
  and My stocks. Selecting a market mover or a saved stock opens research.
  Selecting a search result on My stocks keeps that page open for adding it.
  The URLs support direct visits and browser history.
- **Verification:** Production build, lint, formatting, and route rendering
  checks passed. Each route rendered its own content and excluded the other
  page sections. Direct HTTP requests to all three local frontend URLs
  returned the app. A browser preview surface was unavailable for visual QA.
- **Boundary:** The market movers remain a screened, timestamped Yahoo data
  set. This step changes navigation and layout, not stock ranking logic.

## Step 19 — NIFTY 50 and SENSEX market benchmarks

- **Purpose:** Put broad Indian market context above the top gainers and
  losers on the default page.
- **Files:** `backend/app/services/market_data/benchmarks.py`,
  `backend/app/api/v1/market.py`, `backend/tests/test_market_benchmarks.py`,
  `frontend/src/MarketBenchmarks.tsx`, `frontend/src/MarketBenchmarks.css`,
  `frontend/src/api.ts`, `frontend/src/App.tsx`, the frontend route check,
  and README files.
- **How it works:** The backend asks Yahoo Finance for one month of daily
  NIFTY 50 and SENSEX bars, compares the two latest available values for each,
  and returns point and percentage changes with the latest bar date and source.
  Each index can be unavailable independently. The combined response is
  cached for five minutes. React displays the values as index points, with
  source links and a note that the current daily bar may still change.
- **Verification:** 64 backend tests passed, including offline calculations,
  cache behavior, unavailable data, and endpoint shape. Alembic reported no
  schema changes. The frontend build, lint, formatting, and route rendering
  checks passed. The live local endpoint returned dated values for both
  indices and the frontend returned HTTP 200.
- **Boundary:** These are Yahoo daily index values, not live exchange feeds or
  investment recommendations. No new database table or ML model was added.
