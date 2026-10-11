import pytest
from app.ingestion.normaliser import Normaliser


def test_currency_and_decimal_cleaning():
    obs = Normaliser.normalise("$1,299.99", availability=True)
    assert obs.price == 1299.99
    assert obs.currency == "USD"
    assert obs.availability is True
    assert obs.is_quarantined is False


def test_inr_rupee_cleaning():
    obs = Normaliser.normalise("₹ 54,999.00", availability=True)
    assert obs.price == 54999.00
    assert obs.currency == "INR"
    assert obs.is_quarantined is False


def test_european_format_cleaning():
    obs = Normaliser.normalise("€ 1.450,50", availability=True)
    assert obs.price == 1450.50
    assert obs.currency == "EUR"
    assert obs.is_quarantined is False


def test_quarantine_extreme_jump():
    # 50% deviation threshold: 100 jumping to 200 is 100% change -> should quarantine
    obs = Normaliser.normalise("$200.00", availability=True, last_known_price=100.00)
    assert obs.is_quarantined is True
    assert "Extreme deviation" in obs.quarantine_reason


def test_quarantine_invalid_price():
    obs = Normaliser.normalise("$0.00", availability=False)
    assert obs.is_quarantined is True
