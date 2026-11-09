"""FastAPI application entry point."""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.v1.stocks import router as stocks_router
from app.api.v1.market import router as market_router
from app.api.v1.watchlist import router as watchlist_router
from app.core.config import Settings
from app.db.connection import create_database_engine, database_is_ready
from app.db.session import create_session_factory
from app.services.market_data.provider import MarketDataError


class HealthResponse(BaseModel):
    """Response for the API liveness check."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Response for the database readiness check."""

    status: Literal["ready", "not_ready"]
    database: Literal["connected", "unavailable"]


settings = Settings()
engine = create_database_engine(
    settings.database_url.get_secret_value() if settings.database_url else None
)
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)
app.state.session_factory = create_session_factory(engine)
app.include_router(stocks_router)
app.include_router(market_router)
app.include_router(watchlist_router)


@app.exception_handler(MarketDataError)
async def market_data_error_handler(request: Request, exc: MarketDataError) -> JSONResponse:
    """Expose an upstream failure without leaking provider internals to clients."""

    return JSONResponse(
        status_code=502, content={"detail": "Market data provider request failed"}
    )


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Confirm that the API process can respond to requests."""

    return HealthResponse(status="ok")


@app.get(
    "/api/v1/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
    tags=["health"],
)
def readiness() -> ReadinessResponse | JSONResponse:
    """Report whether PostgreSQL is available for database-backed requests."""

    if database_is_ready(engine):
        return ReadinessResponse(status="ready", database="connected")

    response = ReadinessResponse(status="not_ready", database="unavailable")
    return JSONResponse(status_code=503, content=response.model_dump())
