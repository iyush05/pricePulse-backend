import pytest
from app.ingestion.url_resolver import URLResolver


def test_amazon_asin_extraction():
    url = "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY?tag=affiliate-21&ref=sr_1_1"
    resolved = URLResolver.resolve(url)
    assert resolved.platform == "amazon"
    assert resolved.product_identifier == "B0CHX1W1XY"
    assert resolved.region == "IN"
    assert resolved.canonical_key == "amazon:IN:B0CHX1W1XY"
    assert "tag=" not in resolved.clean_url
    assert "ref=" not in resolved.clean_url


def test_amazon_us_extraction():
    url = "https://www.amazon.com/Sony-WH-1000XM5-Canceling-Headphones/dp/B09XS7JWHH?utm_source=twitter"
    resolved = URLResolver.resolve(url)
    assert resolved.platform == "amazon"
    assert resolved.product_identifier == "B09XS7JWHH"
    assert resolved.region == "US"
    assert resolved.canonical_key == "amazon:US:B09XS7JWHH"


def test_flipkart_pid_extraction():
    url = "https://www.flipkart.com/apple-macbook-air-m2/p/itm12345678abcdef?pid=COMGABCD1234"
    resolved = URLResolver.resolve(url)
    assert resolved.platform == "flipkart"
    assert resolved.product_identifier == "itm12345678abcdef"
    assert resolved.canonical_key == "flipkart:itm12345678abcdef"


def test_tracking_parameter_stripping():
    raw = "https://example.com/product/123?utm_campaign=summer&utm_medium=cpc&real_param=active"
    clean = URLResolver.strip_tracking_parameters(raw)
    assert "utm_campaign" not in clean
    assert "utm_medium" not in clean
    assert "real_param=active" in clean
