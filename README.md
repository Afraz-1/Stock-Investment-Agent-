# EquityIQ

EquityIQ is an investment research and education project for Indian equities.
The project is being built one step at a time so each part can be understood and reviewed.
See [the build log](docs/BUILD_LOG.md) for the purpose, files, and verification
of each completed step.

## Current local app (Step 22)

Start PostgreSQL, then run the API in one terminal:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Run the React frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173/>. Search for an NSE or BSE listing, select it,
and compare live Yahoo price history with rows saved in PostgreSQL. The saved
tab reads `GET /api/v1/stocks/{exchange}/{symbol}/saved-prices` for the chosen
inclusive date range; it never imports new rows. Use My stocks to add a listing
and save its price history; the Step 13 and 14 commands remain optional.
The page starts with NSE:TCS as an example. If that listing is not registered,
the saved tab will have no bars; live lookup can still work.

### Market overview

The default page shows NIFTY 50 and SENSEX cards above the movers list.
`GET /api/v1/market/benchmarks` returns the latest available Yahoo daily bar
for each index, its previous available bar, point and percentage change, and
the bar's date. The cards are index **points**, not rupee prices. The current
day's daily bar can still change during market hours. Each index has an
explicit unavailable state if its Yahoo data is missing; results are cached
for five minutes.

The landing section shows the five largest daily gainers and losers from a
**screened NSE universe**, using Yahoo Finance quotes. The screen is limited
to NSE equities with reported market capitalization of at least ₹10,000 crore
and daily volume of at least 100,000 shares. The API requests leading
candidates in both directions, validates exchange/currency/quote fields,
keeps one latest trading date, and ranks the returned quotes by Yahoo's daily
percentage change. It caches a result for five minutes to avoid a Yahoo
request on every page view. The interface shows quote time and criteria.
Click a mover to open its research view. This is a discovery list, not an
exhaustive NSE ranking or a buy/sell recommendation. Prices can be delayed or
unavailable. The endpoint is `GET /api/v1/market/movers`.

The frontend uses a dark editorial hero and a clean market table, with
responsive layouts informed by the supplied references. Yahoo data is used
for personal research; licensing and a suitable market-data provider must be
reviewed before a public release.

### Company facts

Stock research now shows Yahoo-reported market capitalization, trailing P/E,
price to book, and 52-week low/high. These fields are returned with the
existing `GET /api/v1/stocks/{exchange}/{symbol}/profile` response, so the
frontend does not make another provider request. The adapter keeps missing,
non-finite, non-positive, or inconsistent values unavailable. The snapshot
shows retrieval time and source; Yahoo does not supply verified reporting
periods for these facts, so check company filings before relying on them.

### Annual financials and derived metrics

Stock research now includes up to three annual income and cash-flow statement
columns from `GET /api/v1/stocks/{exchange}/{symbol}/annual-financials`.
It displays revenue, operating income, net income, operating cash flow, and
capital expenditure in the statement currency. The response keeps the annual
period end and marks unknown period starts, publication dates, and accounting
basis explicitly. The source is Yahoo Finance, cached for fifteen minutes.

The backend calculates operating margin, net margin, year-over-year revenue
growth, and free cash flow from the normalized rows. Each result includes the
formula, input values and period ends, calculation time, and an unavailable
reason when needed. Free cash flow is operating cash flow plus Yahoo's negative
capital expenditure outflow. Generic metrics are not calculated for Financial
Services listings. Figures are educational and must be checked against company
filings before investment decisions.

### My stocks

The website now includes a personal tracked-stocks list. Search for a listing,
select it, check its legal company name and optional ISIN against the exchange
listing, and use
**Add to My stocks**. The API verifies that Yahoo recognizes the exact
exchange/symbol before registering it locally. Select a tracked stock and
press **Save 1M/3M/1Y price history** to import that chart range on demand.
The saved-price tab and stored-day count then update. Removing a stock from
My stocks removes only its watchlist membership; its company, security, and
daily price rows remain in PostgreSQL. Re-adding it restores access to those
saved rows. The Step 16 migration adds `watchlist_items` and initially tracks
listings registered before this feature, including NSE:TCS on this machine.

The watchlist and refresh routes are intended for the local personal app. They
have no user authentication yet and must be secured before public deployment.

For now this is a personal research app. It has no accounts, portfolio,
recommendations, ML model, RAG, trade execution, or public deployment.

## Step 1: FastAPI foundation

This step provides a small API with a liveness endpoint. It does not connect to a database
or a market data provider yet.

Requires Python 3.12 or newer.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/api/v1/health> for the health response or
<http://127.0.0.1:8000/docs> for the interactive API documentation.

Run the test from the `backend` directory:

```powershell
python -m pytest
```

The health endpoint checks only that the API process is running. A database readiness
check will be added when the database is introduced.

## Step 2: Configuration

The API title, version, and debug flag are loaded from `backend/app/core/config.py`.
Defaults work without any configuration file. To override them locally, copy the
example file from the project root before starting the API:

```powershell
Copy-Item .env.example .env
```

Edit `.env` as needed. Each setting can also be supplied as an environment variable
with the `EQUITYIQ_` prefix. Environment variables take priority over `.env` values.
The `.env` file is ignored by Git.

## Step 3: Database connectivity

Set `EQUITYIQ_DATABASE_URL` in the project root `.env` when a PostgreSQL database is
available. Use a `postgresql+psycopg://` URL, as shown in `.env.example`. The API
creates a SQLAlchemy engine without opening a connection at startup.

`GET /api/v1/health` returns `200` when the API process responds. `GET /api/v1/ready`
executes `SELECT 1` against the configured database: it returns `200` when connected
and `503` when the database is unconfigured or unavailable. The readiness check has
a three-second connection timeout.

The automated readiness test uses an in-memory SQLite database to exercise the SQL
check without network access.

## Step 4: Local PostgreSQL connection

On this development machine, EquityIQ uses the PostgreSQL 17 server at
`127.0.0.1:5432`. A database named `equityiq` and a dedicated login named
`equityiq_app` were created for the API. The local root `.env` file contains the
connection URL and generated login password; it is ignored by Git. Do not copy
that password into source code or commit `.env`.

The live connection was verified by calling `/api/v1/ready` and querying
`current_user` and `current_database()`; the API connected as `equityiq_app` to
`equityiq`. To inspect the same database in pgAdmin, connect to the PostgreSQL 17
server on `127.0.0.1:5432` and open the `equityiq` database. You can use pgAdmin's
Query Tool to run `SELECT current_database();`.

## Step 5: Database sessions

`backend/app/db/session.py` creates a SQLAlchemy session factory bound to the
configured engine. Future database-backed routes can declare
`db: Annotated[Session, Depends(get_db)]`. FastAPI will provide one session for
the request, and `get_db` will close it afterward. A missing database
configuration produces HTTP 503 for routes using this dependency.

`backend/app/db/base.py` provides the SQLAlchemy base class for future models.
The base class itself does not create tables. Each write operation will need an explicit commit;
the dependency only manages session lifetime.

## Step 6: First table and migration

`backend/app/models/company.py` defines a company independently of its exchange
listings. The `companies` table stores its legal name, two-letter country code,
and timezone-aware creation and update timestamps. Tickers and exchanges will be
stored in separate tables in later steps.

Alembic applies the versioned schema change in
`backend/alembic/versions/20261106_0001_create_companies.py`. From the `backend`
directory, run:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

On this development machine, revision `20261106_0001` has been applied. In
pgAdmin, expand `equityiq > Schemas > public > Tables` to view `companies` and
`alembic_version`. The latter records which migration has been applied. The
company table is empty; a temporary ORM insert was rolled back after verification.

## Step 7: Exchange and security identity

`backend/app/models/exchange.py` defines market venues such as NSE and BSE.
`backend/app/models/security.py` defines one company's listing on one exchange,
including its exchange symbol, optional ISIN, trading currency, and active status.
Foreign keys connect each security to a company and exchange. A unique constraint
prevents the same symbol from appearing twice on the same exchange while allowing
it on different exchanges.

Run `python -m alembic upgrade head` from `backend` to apply revision
`20261107_0002`. In pgAdmin, the `public` schema now also contains `exchanges`
and `securities`. Both are empty; verification inserts were rolled back. The
market-data provider and stock API routes have not been added yet.

## Step 8: Market-data provider contract

`backend/app/services/market_data/provider.py` defines the operations every
market-data adapter must support: search listings, fetch one exact listing's
profile, and fetch daily prices. `schemas.py` defines the normalized results.
Every listing uses both exchange and symbol. Results carry provider and retrieval
time; price history declares its adjustment basis and a reason when no bars are
available. Invalid OHLCV bars and missing timezone information are rejected.

This step only defines the contract. It does not call Yahoo Finance or add stock
API routes. The next adapter will implement this interface.

## Step 9: Yahoo Finance adapter

`backend/app/services/market_data/yahoo.py` implements the provider contract
using `yfinance`. Search returns NSE and BSE equity listings, profiles are
checked against the exact exchange symbol, and daily OHLCV prices are returned
in the normalized Step 8 format. A requested end date is included even though
Yahoo's API treats its end date as exclusive. The adapter asks yfinance for
dividend-adjusted prices and reports provider failures separately from missing
data. Results include their Yahoo source and retrieval time.

From `backend`, use the project virtual environment to run `python -m pytest -q`.
The adapter can also be called directly from Python; it is not exposed through
an API route or saved in PostgreSQL yet. Yahoo data via yfinance is intended for
[personal research use](https://github.com/ranaroussi/yfinance); verify figures
against your brokerage before making a trade.

## Step 10: Stock research API routes

`backend/app/api/v1/stocks.py` exposes the market-data provider through three
read-only endpoints:

- `GET /api/v1/stocks/search?q=TCS&limit=10` finds NSE/BSE listings.
- `GET /api/v1/stocks/NSE/TCS/profile` shows one company's profile.
- `GET /api/v1/stocks/NSE/TCS/prices?start=2026-11-02&end=2026-11-06`
  returns daily OHLCV bars for an inclusive date range.

Start the API from `backend` with `python -m uvicorn app.main:app --reload`, then
open <http://127.0.0.1:8000/docs> to try these routes. Search results and price
history include their provider source and retrieval time. An unknown profile
returns HTTP 404; invalid inputs return HTTP 422; a provider failure returns
HTTP 502. An empty price range returns a normal response with `no_data`.

These routes call Yahoo Finance for personal research. They do not use the
PostgreSQL tables, sync INDmoney, place trades, or make recommendations.

## Step 11: Daily price table

`backend/app/models/daily_price.py` defines the `daily_prices` PostgreSQL
table. Each row belongs to one `Security` listing and one trading day. It
stores OHLCV values, currency, provider, price adjustment, source retrieval
time, and an optional source URL. A unique constraint prevents duplicate rows
for the same listing, day, provider, and adjustment. Database checks reject
non-positive or out-of-range OHLC values and negative volume.

Apply the migration from `backend` with
`python -m alembic upgrade head`. In pgAdmin, the table is under
`equityiq > Schemas > public > Tables > daily_prices`. You can query it with
`SELECT * FROM daily_prices ORDER BY trading_day DESC;`. The table is empty
until a later ingestion step saves provider results. The live migration reached
revision `20261108_0003` and passed `python -m alembic check`.

## Step 12: Daily price ingestion service

`backend/app/services/market_data/ingestion.py` can fetch daily bars for a
`Security` already registered in PostgreSQL and save them to `daily_prices`.
It checks that the provider returned the requested exchange listing, currency,
and date range. An upsert refreshes existing rows without duplicates and does
not replace a newer retrieval with an older one. The service returns the number
of bars received; the caller must explicitly commit or roll back the session.

For example, given an existing `security_id` and SQLAlchemy session:

```python
count = ingest_daily_prices(db, YahooMarketDataProvider(), security_id, start, end)
db.commit()
```

There is no HTTP endpoint or scheduled ingestion job yet. At the end of Step 12,
the live verification fetched and inserted five TCS bars inside a transaction,
then rolled it back; the local application tables were still empty.

## Step 13: Register a stock listing locally

`backend/app/services/market_data/registration.py` registers an NSE or BSE
security and its company. The local-only command below creates a company and
listing, or returns the existing listing when run again:

```powershell
cd backend
python -m app.cli.register_stock --exchange NSE --symbol TCS --legal-name "Tata Consultancy Services Limited" --isin INE467B01029
```

The [NSE TCS page](https://www.nseindia.com/get-quote/equity/TCS/Tata-Consultancy-Services-Limited)
confirms this example's legal name, symbol, and ISIN. To register another
exchange listing for the same company, pass `--company-id` with the printed
company ID instead of `--legal-name`. Check the legal name and identifier
before registering a different stock; the command does not infer them from
Yahoo data. Registration does not mean a stock is held or recommended.

On this development database, the command registered one TCS NSE listing.
At the end of Step 13, `companies`, `exchanges`, and `securities` each contained
one row; `daily_prices` was empty. The local security ID is `5` (earlier rolled-back
test inserts advanced PostgreSQL's ID sequence). No new migration was needed.

## Step 14: Save daily prices from the local terminal

The local command `backend/app/cli/ingest_prices.py` finds a registered listing
by exchange and symbol, calls the Step 12 ingestion service, and commits the
returned price bars. For the registered TCS example, run from `backend`:

```powershell
python -m app.cli.ingest_prices --exchange NSE --symbol TCS --start 2026-11-02 --end 2026-11-06
```

Both dates are inclusive. The command reports bars received; repeating it
refreshes existing rows without creating duplicates. In pgAdmin, inspect:

```sql
SELECT trading_day, open, high, low, close, volume, provider, adjustment
FROM daily_prices
WHERE security_id = 5
ORDER BY trading_day;
```

The local database now has five TCS price rows for this example. This is
historical research data, not an INDmoney holding, trading signal, or order.
The stock API routes still fetch directly from Yahoo; they do not yet read
saved prices.
