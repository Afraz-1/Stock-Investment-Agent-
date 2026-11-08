# EquityIQ

EquityIQ is an investment research and education project for Indian equities.
The project is being built one step at a time so each part can be understood and reviewed.
See [the build log](docs/BUILD_LOG.md) for the purpose, files, and verification
of each completed step.

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
