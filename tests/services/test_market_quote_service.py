from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from src.core.enums import CryptoAsset, Currency
from src.services.market_quote import (
    MARKET_QUOTE_SOURCE,
    MARKET_QUOTE_TTL_SECONDS,
    CachedMarketQuote,
    MarketQuoteService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_service() -> tuple[MarketQuoteService, SimpleNamespace]:
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
    )
    service = MarketQuoteService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=redis_repository,
        translator_hub=SimpleNamespace(),
    )
    return service, redis_repository


def test_get_asset_usd_quote_returns_static_quote_for_pegged_assets_without_cache_or_network(
) -> None:
    service, redis_repository = build_service()

    usdt_quote = run_async(service.get_asset_usd_quote(CryptoAsset.USDT))
    usdc_quote = run_async(service.get_asset_usd_quote(CryptoAsset.USDC))

    assert usdt_quote.price == Decimal("1")
    assert usdc_quote.price == Decimal("1")
    assert usdt_quote.source == "STATIC"
    assert usdc_quote.source == "STATIC"
    assert redis_repository.get.await_count == 0
    assert redis_repository.set.await_count == 0


def test_get_asset_usd_quote_returns_cached_data_when_available() -> None:
    service, redis_repository = build_service()
    redis_repository.get = AsyncMock(
        return_value=CachedMarketQuote(
            price="123.45",
            source="CACHE",
            provider_count=2,
            providers=["binance", "okx"],
            quote_expires_at="2026-04-13T10:00:00+00:00",
        )
    )

    quote = run_async(service.get_asset_usd_quote(CryptoAsset.BTC))

    assert quote.price == Decimal("123.45")
    assert quote.source == "CACHE"
    assert quote.providers == ("binance", "okx")
    assert redis_repository.set.await_count == 0


def test_get_usd_rub_quote_reads_from_cache_when_available() -> None:
    service, redis_repository = build_service()
    redis_repository.get = AsyncMock(
        return_value=CachedMarketQuote(
            price="98.70",
            source="CBR",
            provider_count=1,
            providers=["cbr"],
            quote_expires_at="2026-04-13T10:00:00+00:00",
        )
    )

    quote = run_async(service.get_usd_rub_quote())

    assert quote.price == Decimal("98.70")
    assert quote.source == "CBR"
    assert redis_repository.set.await_count == 0


def test_get_usd_rub_quote_fetches_and_caches_cbr_result() -> None:
    service, redis_repository = build_service()

    class FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self.content = payload

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        async def get(self, url: str):
            assert url == "https://www.cbr-xml-daily.ru/daily_json.js"
            return FakeResponse(b'{"Valute":{"USD":{"Value":91.25}}}')

    with patch("src.services.market_quote_sources.AsyncClient", return_value=FakeClient()):
        quote = run_async(service.get_usd_rub_quote())

    assert quote.price == Decimal("91.25")
    assert quote.source == "CBR"
    redis_repository.set.assert_awaited_once()
    assert redis_repository.set.await_args.kwargs["ex"] == MARKET_QUOTE_TTL_SECONDS


def test_run_provider_tolerates_http_and_payload_errors_and_empty_quotes() -> None:
    service, _redis_repository = build_service()
    client = SimpleNamespace()

    async def http_failure(_client, _asset):
        raise httpx.HTTPError("boom")

    async def payload_failure(_client, _asset):
        raise ValueError("bad payload")

    async def empty_quote(_client, _asset):
        return None

    async def zero_quote(_client, _asset):
        return Decimal("0")

    async def valid_quote(_client, _asset):
        return Decimal("12.34")

    assert (
        run_async(service._run_provider("binance", client, CryptoAsset.BTC, http_failure))
        is None
    )
    assert (
        run_async(service._run_provider("okx", client, CryptoAsset.BTC, payload_failure))
        is None
    )
    assert (
        run_async(service._run_provider("gate", client, CryptoAsset.BTC, empty_quote))
        is None
    )
    assert (
        run_async(service._run_provider("mexc", client, CryptoAsset.BTC, zero_quote))
        is None
    )
    assert run_async(service._run_provider("bybit", client, CryptoAsset.BTC, valid_quote)) == (
        "bybit",
        Decimal("12.34"),
    )


def test_aggregate_market_quotes_preserves_outlier_filtering_and_max_selection() -> None:
    service, _redis_repository = build_service()

    filtered_price, filtered_providers = service._aggregate_market_quotes(
        [
            ("binance", Decimal("100")),
            ("okx", Decimal("101")),
            ("mexc", Decimal("150")),
        ]
    )
    tied_price, tied_providers = service._aggregate_market_quotes(
        [
            ("binance", Decimal("100")),
            ("okx", Decimal("100")),
            ("mexc", Decimal("99")),
        ]
    )

    assert filtered_price == Decimal("101")
    assert filtered_providers == ("okx",)
    assert tied_price == Decimal("100")
    assert tied_providers == ("binance", "okx")


def test_conversion_methods_preserve_rate_math_and_quote_metadata() -> None:
    service, _redis_repository = build_service()
    usd_rub_quote = SimpleNamespace(
        price=Decimal("100"),
        source="CBR",
        provider_count=1,
        quote_expires_at="2026-04-13T10:00:00+00:00",
    )
    asset_quote = SimpleNamespace(
        price=Decimal("2"),
        source=MARKET_QUOTE_SOURCE,
        provider_count=3,
        quote_expires_at="2026-04-13T09:59:00+00:00",
    )
    service.get_usd_rub_quote = AsyncMock(return_value=usd_rub_quote)  # type: ignore[method-assign]
    service.get_asset_usd_quote = AsyncMock(return_value=asset_quote)  # type: ignore[method-assign]

    from_usd = run_async(
        service.convert_from_usd(amount_usd=Decimal("10"), target_currency=Currency.RUB)
    )
    from_rub = run_async(
        service.convert_from_rub(amount_rub=Decimal("200"), target_currency=Currency.TON)
    )
    to_rub = run_async(service.convert_to_rub(amount=Decimal("3"), source_currency=Currency.TON))

    assert from_usd.amount == Decimal("1000")
    assert from_usd.quote_source == "CBR"
    assert from_rub.amount == Decimal("1.000000")
    assert from_rub.quote_source == "CBR+MARKET_MAX_REAL"
    assert from_rub.quote_provider_count == 4
    assert to_rub.amount == Decimal("600")
    assert to_rub.quote_rate == Decimal("200")
    assert to_rub.quote_source == "CBR+MARKET_MAX_REAL"


def test_normalize_amount_preserves_currency_specific_quantization_and_minimums() -> None:
    service, _redis_repository = build_service()

    assert service._normalize_amount(Decimal("0.004"), Currency.USD) == Decimal("0.01")
    assert service._normalize_amount(Decimal("0.4"), Currency.RUB) == Decimal("1")
    assert service._normalize_amount(Decimal("0.000000001"), Currency.BTC) == Decimal("0.00000001")
    assert service._normalize_amount(Decimal("0.0000004"), Currency.TON) == Decimal("0.000001")
    assert service._normalize_amount(Decimal("-1"), Currency.USD) == Decimal("0")


def test_currency_to_asset_raises_for_non_crypto_currency() -> None:
    service, _redis_repository = build_service()

    try:
        service._currency_to_asset(Currency.RUB)
    except ValueError as exception:
        assert "is not a market crypto asset" in str(exception)
    else:
        raise AssertionError("Expected non-crypto currency to raise ValueError")
