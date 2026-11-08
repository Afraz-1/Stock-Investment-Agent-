"""Tests for typed environment configuration."""

from pytest import MonkeyPatch

from app.core.config import Settings


def test_settings_use_defaults_when_no_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("EQUITYIQ_APP_NAME", raising=False)
    monkeypatch.delenv("EQUITYIQ_APP_VERSION", raising=False)
    monkeypatch.delenv("EQUITYIQ_DEBUG", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "EquityIQ API"
    assert settings.app_version == "0.1.0"
    assert settings.debug is False


def test_settings_read_environment_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("EQUITYIQ_APP_NAME", "EquityIQ Test API")
    monkeypatch.setenv("EQUITYIQ_DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.app_name == "EquityIQ Test API"
    assert settings.debug is True
