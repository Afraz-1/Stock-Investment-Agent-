"""Portfolio accounting and journal routes with a local SQLite database."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models import Base, Company, Exchange, Security, WatchlistItem


def _client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'portfolio.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        company = Company(legal_name="Example Limited", country_code="IN")
        exchange = Exchange(code="NSE", name="National Stock Exchange", country_code="IN", timezone_name="Asia/Kolkata")
        db.add_all([company, exchange])
        db.flush()
        security = Security(company_id=company.id, exchange_id=exchange.id, symbol="EXAMPLE", currency_code="INR")
        db.add(security)
        db.flush()
        db.add(WatchlistItem(security_id=security.id))
        db.commit()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    return TestClient(app), engine


def _trade(side: str, quantity: str, price: str, day: str = "2026-01-05") -> dict:
    return {"security": {"exchange_code": "NSE", "symbol": "EXAMPLE"},
            "trade_day": day, "side": side, "quantity": quantity, "price": price, "fees": "1"}


def test_portfolio_holdings_sales_and_journal(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        assert client.get("/api/v1/portfolio").json() == {"holdings": [], "trades": [], "journal": [], "realized_pnl": "0"}
        assert client.post("/api/v1/portfolio/trades", json=_trade("buy", "10", "100")).status_code == 201
        assert client.post("/api/v1/portfolio/trades", json=_trade("sell", "4", "120", "2026-01-06")).status_code == 201
        body = client.get("/api/v1/portfolio").json()
        assert body["holdings"][0]["quantity"] == "6.000000"
        assert Decimal(body["holdings"][0]["cost_basis"]) == Decimal("600.60")
        assert Decimal(body["realized_pnl"]) == Decimal("78.60")
        added = client.post("/api/v1/portfolio/journal", json={"security": _trade("buy", "1", "1")["security"], "thesis": "Revenue and cash flow appear resilient"})
        assert added.status_code == 201
        entry_id = added.json()["id"]
        changed = client.patch(f"/api/v1/portfolio/journal/{entry_id}", json={"outcome": "Thesis needs revision after results"})
        assert changed.status_code == 200
        assert client.get("/api/v1/portfolio").json()["journal"][0]["outcome"] == "Thesis needs revision after results"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_rejects_oversell_even_when_trade_is_backdated(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        client.post("/api/v1/portfolio/trades", json=_trade("buy", "2", "100", "2026-01-05"))
        assert client.post("/api/v1/portfolio/trades", json=_trade("sell", "3", "110", "2026-01-06")).status_code == 422
        assert client.post("/api/v1/portfolio/trades", json=_trade("sell", "1", "110", "2026-01-04")).status_code == 422
        assert len(client.get("/api/v1/portfolio").json()["trades"]) == 1
        assert client.post("/api/v1/portfolio/trades", json=_trade("buy", "0", "100")).status_code == 422
        buy_id = client.get("/api/v1/portfolio").json()["trades"][0]["id"]
        assert client.delete(f"/api/v1/portfolio/trades/{buy_id}").status_code == 204
        assert client.get("/api/v1/portfolio").json()["trades"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_cannot_delete_buy_that_supports_later_sell(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        buy = client.post("/api/v1/portfolio/trades", json=_trade("buy", "2", "100"))
        assert buy.status_code == 201
        assert client.post("/api/v1/portfolio/trades", json=_trade("sell", "1", "110", "2026-01-06")).status_code == 201
        assert client.delete(f"/api/v1/portfolio/trades/{buy.json()['id']}").status_code == 422
        assert len(client.get("/api/v1/portfolio").json()["trades"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
