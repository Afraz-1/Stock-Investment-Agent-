"""The local command commits retrieved bars and reports input failures."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.cli.ingest_prices import main
from app.models import Base, DailyPrice
from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.registration import register_listing
from app.services.market_data.schemas import (
    MarketDataSource,
    PriceBar,
    PriceHistory,
    SecurityKey,
)


@pytest.fixture
def command_context(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'prices.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        listing = register_listing(
            db, exchange_code="NSE", symbol="TCS",
            legal_name="Tata Consultancy Services Limited",
        )
        security_id = listing.id
        db.commit()

    provider = Mock(spec=MarketDataProvider)
    provider.get_prices.return_value = PriceHistory(
        security=SecurityKey(exchange_code="NSE", symbol="TCS"),
        currency_code="INR",
        adjustment="dividend_adjusted",
        bars=[
            PriceBar(
                trading_day=date(2026, 11, 5),
                open=Decimal("100"), high=Decimal("105"), low=Decimal("99"),
                close=Decimal("103"), volume=1000,
            ),
            PriceBar(
                trading_day=date(2026, 11, 6),
                open=Decimal("102"), high=Decimal("106"), low=Decimal("101"),
                close=Decimal("104"), volume=1100,
            ),
        ],
        source=MarketDataSource(
            provider="test_provider",
            retrieved_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
        ),
    )
    monkeypatch.setattr("app.cli.ingest_prices.create_database_engine", lambda url: engine)
    monkeypatch.setattr("app.cli.ingest_prices.YahooMarketDataProvider", lambda: provider)
    yield engine, provider, security_id
    engine.dispose()


def test_command_commits_prices_without_duplicate_rows(command_context, capsys) -> None:
    engine, provider, security_id = command_context
    args = [
        "--exchange", "NSE", "--symbol", "tcs",
        "--start", "2026-11-05", "--end", "2026-11-06",
    ]
    main(args)
    assert f"Received 2 daily bars for NSE:TCS (security ID {security_id})" in capsys.readouterr().out
    provider.get_prices.assert_called_with(
        SecurityKey(exchange_code="NSE", symbol="TCS"),
        date(2026, 11, 5), date(2026, 11, 6),
    )
    main(args)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DailyPrice)) == 2
        assert [row.trading_day for row in db.scalars(select(DailyPrice).order_by(DailyPrice.trading_day))] == [
            date(2026, 11, 5), date(2026, 11, 6)
        ]


def test_unregistered_listing_never_calls_provider(command_context, capsys) -> None:
    engine, provider, _ = command_context
    with pytest.raises(SystemExit) as exit_info:
        main([
            "--exchange", "BSE", "--symbol", "TCS",
            "--start", "2026-11-05", "--end", "2026-11-06",
        ])
    assert exit_info.value.code == 2
    assert "not registered" in capsys.readouterr().err
    provider.get_prices.assert_not_called()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0


@pytest.mark.parametrize(
    "dates",
    [
        ["--start", "20261105", "--end", "2026-11-06"],
        ["--start", "2026-11-06", "--end", "2026-11-05"],
    ],
)
def test_bad_dates_stop_before_fetch(command_context, dates, capsys) -> None:
    _, provider, _ = command_context
    with pytest.raises(SystemExit) as exit_info:
        main(["--exchange", "NSE", "--symbol", "TCS", *dates])
    assert exit_info.value.code == 2
    provider.get_prices.assert_not_called()


def test_provider_failure_does_not_save_prices(command_context, capsys) -> None:
    engine, provider, _ = command_context
    provider.get_prices.side_effect = MarketDataError("private upstream detail")
    with pytest.raises(SystemExit) as exit_info:
        main([
            "--exchange", "NSE", "--symbol", "TCS",
            "--start", "2026-11-05", "--end", "2026-11-06",
        ])
    assert exit_info.value.code == 2
    assert "Market data provider request failed" in capsys.readouterr().err
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0
