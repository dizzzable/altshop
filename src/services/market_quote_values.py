from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any, Iterable, Sequence

from src.core.enums import CryptoAsset, Currency
from src.core.utils.time import datetime_now

from .market_quote import (
    BTC_QUANTUM,
    INTEGER_QUANTUM,
    MARKET_QUOTE_TTL_SECONDS,
    SIX_DECIMAL_QUANTUM,
    STATIC_QUOTE_SOURCE,
    USD_QUANTUM,
    CachedMarketQuote,
    CurrencyConversionQuote,
    MarketQuoteSnapshot,
)


def aggregate_market_quotes(
    quotes: Iterable[tuple[str, Decimal]],
) -> tuple[Decimal, tuple[str, ...]]:
    normalized = [(provider, price) for provider, price in quotes if price > 0]
    if not normalized:
        raise ValueError("No valid market quotes were collected")

    prices = [price for _, price in normalized]
    if len(prices) >= 3:
        median_price = median(prices)
        lower_bound = median_price * Decimal("0.9")
        upper_bound = median_price * Decimal("1.1")
        filtered = [
            (provider, price)
            for provider, price in normalized
            if lower_bound <= price <= upper_bound
        ]
        if filtered:
            normalized = filtered

    max_price = max(price for _, price in normalized)
    providers = tuple(sorted(provider for provider, price in normalized if price == max_price))
    if not providers:
        providers = tuple(sorted(provider for provider, _ in normalized))
    return max_price, providers


def build_market_quote(
    *,
    price: Decimal,
    source: str,
    providers: Sequence[str],
) -> MarketQuoteSnapshot:
    quote_expires_at = quote_expires_at_value()
    return MarketQuoteSnapshot(
        price=price,
        source=source,
        provider_count=len(providers),
        providers=tuple(providers),
        quote_expires_at=quote_expires_at,
    )


def build_static_market_quote(*, price: Decimal) -> MarketQuoteSnapshot:
    return build_market_quote(
        price=price,
        source=STATIC_QUOTE_SOURCE,
        providers=(),
    )


def build_static_conversion(
    *,
    amount: Decimal,
    currency: Currency,
) -> CurrencyConversionQuote:
    normalized_amount = normalize_amount(amount, currency)
    return CurrencyConversionQuote(
        amount=normalized_amount,
        currency=currency,
        quote_rate=Decimal("1"),
        quote_source=STATIC_QUOTE_SOURCE,
        quote_provider_count=0,
        quote_expires_at=quote_expires_at_value(),
    )


def quote_expires_at_value() -> str:
    return (
        (datetime_now() + timedelta(seconds=MARKET_QUOTE_TTL_SECONDS))
        .replace(microsecond=0)
        .isoformat()
    )


def quote_to_cache(snapshot: MarketQuoteSnapshot) -> CachedMarketQuote:
    return CachedMarketQuote(
        price=str(snapshot.price),
        source=snapshot.source,
        provider_count=snapshot.provider_count,
        providers=list(snapshot.providers),
        quote_expires_at=snapshot.quote_expires_at,
    )


def restore_quote_from_cache(cached: CachedMarketQuote) -> MarketQuoteSnapshot:
    return MarketQuoteSnapshot(
        price=Decimal(cached.price),
        source=cached.source,
        provider_count=cached.provider_count,
        providers=tuple(cached.providers),
        quote_expires_at=cached.quote_expires_at,
    )


def merge_sources(*quotes: MarketQuoteSnapshot) -> str:
    parts = [quote.source for quote in quotes if quote.source]
    return "+".join(parts) if parts else STATIC_QUOTE_SOURCE


def currency_to_asset(currency: Currency) -> CryptoAsset:
    try:
        return CryptoAsset(currency.value)
    except ValueError as exception:
        raise ValueError(
            f"Currency '{currency.value}' is not a market crypto asset"
        ) from exception


def median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def optional_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "0", 0):
        return None
    try:
        parsed = to_decimal(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def normalize_amount(amount: Decimal, currency: Currency) -> Decimal:
    quantum = USD_QUANTUM
    minimum = USD_QUANTUM
    if currency in {Currency.RUB, Currency.XTR}:
        quantum = INTEGER_QUANTUM
        minimum = INTEGER_QUANTUM
    elif currency == Currency.BTC:
        quantum = BTC_QUANTUM
        minimum = BTC_QUANTUM
    elif currency not in {Currency.USD, Currency.USDT, Currency.USDC}:
        quantum = SIX_DECIMAL_QUANTUM
        minimum = SIX_DECIMAL_QUANTUM

    if amount <= 0:
        return Decimal(0)

    normalized = amount.quantize(quantum, rounding=ROUND_DOWN)
    if normalized < minimum:
        return minimum
    return normalized
