from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Awaitable, Callable

from httpx import AsyncClient
from pydantic import BaseModel

from src.core.enums import CryptoAsset, Currency

from .base import BaseService

MARKET_QUOTE_TTL_SECONDS = 60
STATIC_QUOTE_SOURCE = "STATIC"
MARKET_QUOTE_SOURCE = "MARKET_MAX_REAL"
FIAT_QUOTE_SOURCE = "CBR"
SUPPORTED_MARKET_CURRENCIES: tuple[Currency, ...] = (
    Currency.USD,
    Currency.RUB,
    Currency.USDT,
    Currency.TON,
    Currency.BTC,
    Currency.ETH,
    Currency.LTC,
    Currency.BNB,
    Currency.DASH,
    Currency.SOL,
    Currency.XMR,
    Currency.USDC,
    Currency.TRX,
)
PEGGED_ASSET_USD_PRICE = Decimal("1")
USD_QUANTUM = Decimal("0.01")
BTC_QUANTUM = Decimal("0.00000001")
SIX_DECIMAL_QUANTUM = Decimal("0.000001")
INTEGER_QUANTUM = Decimal("1")


class CachedMarketQuote(BaseModel):
    price: str
    source: str
    provider_count: int
    providers: list[str]
    quote_expires_at: str


@dataclass(slots=True, frozen=True)
class MarketQuoteSnapshot:
    price: Decimal
    source: str
    provider_count: int
    providers: tuple[str, ...]
    quote_expires_at: str


@dataclass(slots=True, frozen=True)
class CurrencyConversionQuote:
    amount: Decimal
    currency: Currency
    quote_rate: Decimal
    quote_source: str
    quote_provider_count: int
    quote_expires_at: str


from . import market_quote_conversions as _conversions_impl  # noqa: E402
from . import market_quote_sources as _sources_impl  # noqa: E402
from . import market_quote_values as _values_impl  # noqa: E402


class MarketQuoteService(BaseService):
    async def convert_from_usd(
        self,
        *,
        amount_usd: Decimal,
        target_currency: Currency,
    ) -> CurrencyConversionQuote:
        return await _conversions_impl.convert_from_usd(
            self,
            amount_usd=amount_usd,
            target_currency=target_currency,
        )

    async def convert_from_rub(
        self,
        *,
        amount_rub: Decimal,
        target_currency: Currency,
    ) -> CurrencyConversionQuote:
        return await _conversions_impl.convert_from_rub(
            self,
            amount_rub=amount_rub,
            target_currency=target_currency,
        )

    async def convert_to_rub(
        self,
        *,
        amount: Decimal,
        source_currency: Currency,
    ) -> CurrencyConversionQuote:
        return await _conversions_impl.convert_to_rub(
            self,
            amount=amount,
            source_currency=source_currency,
        )

    async def get_asset_usd_quote(self, asset: CryptoAsset) -> MarketQuoteSnapshot:
        return await _sources_impl.get_asset_usd_quote(self, asset)

    async def get_usd_rub_quote(self) -> MarketQuoteSnapshot:
        return await _sources_impl.get_usd_rub_quote(self)

    async def _collect_asset_quotes(self, asset: CryptoAsset) -> list[tuple[str, Decimal]]:
        return await _sources_impl.collect_asset_quotes(self, asset)

    async def _run_provider(
        self,
        provider: str,
        client: AsyncClient,
        asset: CryptoAsset,
        fetcher: Callable[[AsyncClient, CryptoAsset], Awaitable[Decimal | None]],
    ) -> tuple[str, Decimal] | None:
        return await _sources_impl.run_provider(provider, client, asset, fetcher)

    async def _fetch_coinbase_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_coinbase_quote(client, asset)

    async def _fetch_binance_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_binance_quote(client, asset)

    async def _fetch_okx_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_okx_quote(client, asset)

    async def _fetch_bitget_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_bitget_quote(client, asset)

    async def _fetch_upbit_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_upbit_quote(client, asset)

    async def _fetch_gate_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_gate_quote(client, asset)

    async def _fetch_kucoin_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_kucoin_quote(client, asset)

    async def _fetch_mexc_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_mexc_quote(client, asset)

    async def _fetch_htx_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_htx_quote(client, asset)

    async def _fetch_bybit_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        return await _sources_impl.fetch_bybit_quote(client, asset)

    def _aggregate_market_quotes(
        self,
        quotes: list[tuple[str, Decimal]],
    ) -> tuple[Decimal, tuple[str, ...]]:
        return _values_impl.aggregate_market_quotes(quotes)

    def _build_market_quote(
        self,
        *,
        price: Decimal,
        source: str,
        providers: tuple[str, ...] | list[str],
    ) -> MarketQuoteSnapshot:
        return _values_impl.build_market_quote(
            price=price,
            source=source,
            providers=providers,
        )

    def _build_static_market_quote(self, *, price: Decimal) -> MarketQuoteSnapshot:
        return _values_impl.build_static_market_quote(price=price)

    def _build_static_conversion(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> CurrencyConversionQuote:
        return _values_impl.build_static_conversion(amount=amount, currency=currency)

    @staticmethod
    def _quote_expires_at() -> str:
        return _values_impl.quote_expires_at_value()

    @staticmethod
    def _quote_to_cache(snapshot: MarketQuoteSnapshot) -> CachedMarketQuote:
        return _values_impl.quote_to_cache(snapshot)

    @staticmethod
    def _restore_quote_from_cache(cached: CachedMarketQuote) -> MarketQuoteSnapshot:
        return _values_impl.restore_quote_from_cache(cached)

    @staticmethod
    def _merge_sources(*quotes: MarketQuoteSnapshot) -> str:
        return _values_impl.merge_sources(*quotes)

    @staticmethod
    def _currency_to_asset(currency: Currency) -> CryptoAsset:
        return _values_impl.currency_to_asset(currency)

    @staticmethod
    def _median(values: list[Decimal]) -> Decimal:
        return _values_impl.median(values)

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        return _values_impl.to_decimal(value)

    @classmethod
    def _optional_decimal(cls, value: Any) -> Decimal | None:
        return _values_impl.optional_decimal(value)

    @staticmethod
    def _normalize_amount(amount: Decimal, currency: Currency) -> Decimal:
        return _values_impl.normalize_amount(amount, currency)


__all__ = [
    "CurrencyConversionQuote",
    "MARKET_QUOTE_TTL_SECONDS",
    "MarketQuoteService",
    "MarketQuoteSnapshot",
    "SUPPORTED_MARKET_CURRENCIES",
]
