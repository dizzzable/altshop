from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.core.enums import Currency
from src.services.market_quote import CurrencyConversionQuote

if TYPE_CHECKING:
    from .market_quote import MarketQuoteService


async def convert_from_usd(
    service: MarketQuoteService,
    *,
    amount_usd: Decimal,
    target_currency: Currency,
) -> CurrencyConversionQuote:
    if target_currency == Currency.USD:
        return service._build_static_conversion(amount=amount_usd, currency=Currency.USD)

    if target_currency == Currency.RUB:
        usd_rub_quote = await service.get_usd_rub_quote()
        converted_amount = service._normalize_amount(amount_usd * usd_rub_quote.price, Currency.RUB)
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=Currency.RUB,
            quote_rate=usd_rub_quote.price,
            quote_source=usd_rub_quote.source,
            quote_provider_count=usd_rub_quote.provider_count,
            quote_expires_at=usd_rub_quote.quote_expires_at,
        )

    asset_quote = await service.get_asset_usd_quote(service._currency_to_asset(target_currency))
    converted_amount = service._normalize_amount(amount_usd / asset_quote.price, target_currency)
    return CurrencyConversionQuote(
        amount=converted_amount,
        currency=target_currency,
        quote_rate=asset_quote.price,
        quote_source=asset_quote.source,
        quote_provider_count=asset_quote.provider_count,
        quote_expires_at=asset_quote.quote_expires_at,
    )


async def convert_from_rub(
    service: MarketQuoteService,
    *,
    amount_rub: Decimal,
    target_currency: Currency,
) -> CurrencyConversionQuote:
    if target_currency == Currency.RUB:
        return service._build_static_conversion(amount=amount_rub, currency=Currency.RUB)

    usd_rub_quote = await service.get_usd_rub_quote()
    if target_currency == Currency.USD:
        converted_amount = service._normalize_amount(amount_rub / usd_rub_quote.price, Currency.USD)
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=Currency.USD,
            quote_rate=usd_rub_quote.price,
            quote_source=usd_rub_quote.source,
            quote_provider_count=usd_rub_quote.provider_count,
            quote_expires_at=usd_rub_quote.quote_expires_at,
        )

    asset_quote = await service.get_asset_usd_quote(service._currency_to_asset(target_currency))
    rub_per_asset = asset_quote.price * usd_rub_quote.price
    converted_amount = service._normalize_amount(amount_rub / rub_per_asset, target_currency)
    return CurrencyConversionQuote(
        amount=converted_amount,
        currency=target_currency,
        quote_rate=rub_per_asset,
        quote_source=service._merge_sources(usd_rub_quote, asset_quote),
        quote_provider_count=usd_rub_quote.provider_count + asset_quote.provider_count,
        quote_expires_at=min(usd_rub_quote.quote_expires_at, asset_quote.quote_expires_at),
    )


async def convert_to_rub(
    service: MarketQuoteService,
    *,
    amount: Decimal,
    source_currency: Currency,
) -> CurrencyConversionQuote:
    if source_currency == Currency.RUB:
        return service._build_static_conversion(amount=amount, currency=Currency.RUB)

    usd_rub_quote = await service.get_usd_rub_quote()
    if source_currency == Currency.USD:
        converted_amount = service._normalize_amount(amount * usd_rub_quote.price, Currency.RUB)
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=Currency.RUB,
            quote_rate=usd_rub_quote.price,
            quote_source=usd_rub_quote.source,
            quote_provider_count=usd_rub_quote.provider_count,
            quote_expires_at=usd_rub_quote.quote_expires_at,
        )

    asset_quote = await service.get_asset_usd_quote(service._currency_to_asset(source_currency))
    rub_per_asset = asset_quote.price * usd_rub_quote.price
    converted_amount = service._normalize_amount(amount * rub_per_asset, Currency.RUB)
    return CurrencyConversionQuote(
        amount=converted_amount,
        currency=Currency.RUB,
        quote_rate=rub_per_asset,
        quote_source=service._merge_sources(usd_rub_quote, asset_quote),
        quote_provider_count=usd_rub_quote.provider_count + asset_quote.provider_count,
        quote_expires_at=min(usd_rub_quote.quote_expires_at, asset_quote.quote_expires_at),
    )
