from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any, Awaitable, Callable, Iterable, Sequence

import orjson
from httpx import AsyncClient, HTTPError, Timeout
from loguru import logger
from pydantic import BaseModel

from src.core.enums import CryptoAsset, Currency
from src.core.storage.keys import MarketAssetUsdQuoteKey, MarketUsdRubQuoteKey
from src.core.utils.time import datetime_now

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


class MarketQuoteService(BaseService):
    async def convert_from_usd(
        self,
        *,
        amount_usd: Decimal,
        target_currency: Currency,
    ) -> CurrencyConversionQuote:
        if target_currency == Currency.USD:
            return self._build_static_conversion(amount=amount_usd, currency=Currency.USD)

        if target_currency == Currency.RUB:
            usd_rub_quote = await self.get_usd_rub_quote()
            converted_amount = self._normalize_amount(
                amount_usd * usd_rub_quote.price,
                Currency.RUB,
            )
            return CurrencyConversionQuote(
                amount=converted_amount,
                currency=Currency.RUB,
                quote_rate=usd_rub_quote.price,
                quote_source=usd_rub_quote.source,
                quote_provider_count=usd_rub_quote.provider_count,
                quote_expires_at=usd_rub_quote.quote_expires_at,
            )

        asset_quote = await self.get_asset_usd_quote(self._currency_to_asset(target_currency))
        converted_amount = self._normalize_amount(
            amount_usd / asset_quote.price,
            target_currency,
        )
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=target_currency,
            quote_rate=asset_quote.price,
            quote_source=asset_quote.source,
            quote_provider_count=asset_quote.provider_count,
            quote_expires_at=asset_quote.quote_expires_at,
        )

    async def convert_from_rub(
        self,
        *,
        amount_rub: Decimal,
        target_currency: Currency,
    ) -> CurrencyConversionQuote:
        if target_currency == Currency.RUB:
            return self._build_static_conversion(amount=amount_rub, currency=Currency.RUB)

        usd_rub_quote = await self.get_usd_rub_quote()
        if target_currency == Currency.USD:
            converted_amount = self._normalize_amount(
                amount_rub / usd_rub_quote.price,
                Currency.USD,
            )
            return CurrencyConversionQuote(
                amount=converted_amount,
                currency=Currency.USD,
                quote_rate=usd_rub_quote.price,
                quote_source=usd_rub_quote.source,
                quote_provider_count=usd_rub_quote.provider_count,
                quote_expires_at=usd_rub_quote.quote_expires_at,
            )

        asset_quote = await self.get_asset_usd_quote(self._currency_to_asset(target_currency))
        rub_per_asset = asset_quote.price * usd_rub_quote.price
        converted_amount = self._normalize_amount(
            amount_rub / rub_per_asset,
            target_currency,
        )
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=target_currency,
            quote_rate=rub_per_asset,
            quote_source=self._merge_sources(usd_rub_quote, asset_quote),
            quote_provider_count=usd_rub_quote.provider_count + asset_quote.provider_count,
            quote_expires_at=min(usd_rub_quote.quote_expires_at, asset_quote.quote_expires_at),
        )

    async def convert_to_rub(
        self,
        *,
        amount: Decimal,
        source_currency: Currency,
    ) -> CurrencyConversionQuote:
        if source_currency == Currency.RUB:
            return self._build_static_conversion(amount=amount, currency=Currency.RUB)

        usd_rub_quote = await self.get_usd_rub_quote()
        if source_currency == Currency.USD:
            converted_amount = self._normalize_amount(
                amount * usd_rub_quote.price,
                Currency.RUB,
            )
            return CurrencyConversionQuote(
                amount=converted_amount,
                currency=Currency.RUB,
                quote_rate=usd_rub_quote.price,
                quote_source=usd_rub_quote.source,
                quote_provider_count=usd_rub_quote.provider_count,
                quote_expires_at=usd_rub_quote.quote_expires_at,
            )

        asset_quote = await self.get_asset_usd_quote(self._currency_to_asset(source_currency))
        rub_per_asset = asset_quote.price * usd_rub_quote.price
        converted_amount = self._normalize_amount(
            amount * rub_per_asset,
            Currency.RUB,
        )
        return CurrencyConversionQuote(
            amount=converted_amount,
            currency=Currency.RUB,
            quote_rate=rub_per_asset,
            quote_source=self._merge_sources(usd_rub_quote, asset_quote),
            quote_provider_count=usd_rub_quote.provider_count + asset_quote.provider_count,
            quote_expires_at=min(usd_rub_quote.quote_expires_at, asset_quote.quote_expires_at),
        )

    async def get_asset_usd_quote(self, asset: CryptoAsset) -> MarketQuoteSnapshot:
        if asset in {CryptoAsset.USDT, CryptoAsset.USDC}:
            return self._build_static_market_quote(price=PEGGED_ASSET_USD_PRICE)

        cache_key = MarketAssetUsdQuoteKey(asset=asset.value)
        cached = await self.redis_repository.get(cache_key, CachedMarketQuote)
        if cached:
            return self._restore_quote_from_cache(cached)

        quotes = await self._collect_asset_quotes(asset)
        aggregated_price, providers = self._aggregate_market_quotes(quotes)
        snapshot = self._build_market_quote(
            price=aggregated_price,
            source=MARKET_QUOTE_SOURCE,
            providers=providers,
        )
        await self.redis_repository.set(
            cache_key,
            self._quote_to_cache(snapshot),
            ex=MARKET_QUOTE_TTL_SECONDS,
        )
        return snapshot

    async def get_usd_rub_quote(self) -> MarketQuoteSnapshot:
        cache_key = MarketUsdRubQuoteKey()
        cached = await self.redis_repository.get(cache_key, CachedMarketQuote)
        if cached:
            return self._restore_quote_from_cache(cached)

        async with AsyncClient(timeout=Timeout(15.0)) as client:
            response = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
            response.raise_for_status()
            payload = orjson.loads(response.content)

        usd_rate = self._to_decimal(payload["Valute"]["USD"]["Value"])
        snapshot = self._build_market_quote(
            price=usd_rate,
            source=FIAT_QUOTE_SOURCE,
            providers=("cbr",),
        )
        await self.redis_repository.set(
            cache_key,
            self._quote_to_cache(snapshot),
            ex=MARKET_QUOTE_TTL_SECONDS,
        )
        return snapshot

    async def _collect_asset_quotes(self, asset: CryptoAsset) -> list[tuple[str, Decimal]]:
        providers: Sequence[
            tuple[str, Callable[[AsyncClient, CryptoAsset], Awaitable[Decimal | None]]]
        ] = (
            ("coinbase", self._fetch_coinbase_quote),
            ("binance", self._fetch_binance_quote),
            ("okx", self._fetch_okx_quote),
            ("bitget", self._fetch_bitget_quote),
            ("upbit", self._fetch_upbit_quote),
            ("gate", self._fetch_gate_quote),
            ("kucoin", self._fetch_kucoin_quote),
            ("mexc", self._fetch_mexc_quote),
            ("htx", self._fetch_htx_quote),
            ("bybit", self._fetch_bybit_quote),
        )

        async with AsyncClient(timeout=Timeout(12.0)) as client:
            tasks = [
                self._run_provider(provider, client, asset, fetcher)
                for provider, fetcher in providers
            ]
            results = await asyncio.gather(*tasks)

        return [result for result in results if result is not None]

    async def _run_provider(
        self,
        provider: str,
        client: AsyncClient,
        asset: CryptoAsset,
        fetcher: Callable[[AsyncClient, CryptoAsset], Awaitable[Decimal | None]],
    ) -> tuple[str, Decimal] | None:
        try:
            quote = await fetcher(client, asset)
        except HTTPError as exception:
            logger.debug(
                "Market quote provider '{}' failed for asset '{}': {}",
                provider,
                asset.value,
                exception,
            )
            return None
        except Exception as exception:
            logger.debug(
                "Market quote provider '{}' returned invalid payload for asset '{}': {}",
                provider,
                asset.value,
                exception,
            )
            return None

        if quote is None or quote <= 0:
            return None
        return provider, quote

    async def _fetch_coinbase_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            f"https://api.exchange.coinbase.com/products/{asset.value}-USD/book",
            params={"level": 1},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        if not isinstance(payload, dict):
            return None
        ask = payload.get("asks", [[None]])[0][0]
        return self._optional_decimal(ask)

    async def _fetch_binance_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.binance.com/api/v3/ticker/bookTicker",
            params={"symbol": f"{asset.value}USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        return self._optional_decimal(payload.get("askPrice"))

    async def _fetch_okx_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": f"{asset.value}-USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        data = payload.get("data") or []
        if not data:
            return None
        return self._optional_decimal(data[0].get("askPx"))

    async def _fetch_bitget_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.bitget.com/api/v2/spot/market/tickers",
            params={"symbol": f"{asset.value}USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        data = payload.get("data") or []
        if not data:
            return None
        return self._optional_decimal(data[0].get("askPr"))

    async def _fetch_upbit_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        if asset in {CryptoAsset.USDT, CryptoAsset.USDC}:
            return None
        response = await client.get(
            "https://api.upbit.com/v1/ticker",
            params={"markets": f"USDT-{asset.value}"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        if not isinstance(payload, list) or not payload:
            return None
        return self._optional_decimal(payload[0].get("trade_price"))

    async def _fetch_gate_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.gateio.ws/api/v4/spot/tickers",
            params={"currency_pair": f"{asset.value}_USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        if not isinstance(payload, list) or not payload:
            return None
        return self._optional_decimal(payload[0].get("lowest_ask") or payload[0].get("last"))

    async def _fetch_kucoin_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.kucoin.com/api/v1/market/orderbook/level1",
            params={"symbol": f"{asset.value}-USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        data = payload.get("data") or {}
        return self._optional_decimal(data.get("bestAsk") or data.get("price"))

    async def _fetch_mexc_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.mexc.com/api/v3/ticker/bookTicker",
            params={"symbol": f"{asset.value}USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        return self._optional_decimal(payload.get("askPrice"))

    async def _fetch_htx_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.huobi.pro/market/detail/merged",
            params={"symbol": f"{asset.value.lower()}usdt"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        tick = payload.get("tick") or {}
        ask = tick.get("ask")
        if isinstance(ask, list) and ask:
            return self._optional_decimal(ask[0])
        return self._optional_decimal(tick.get("close"))

    async def _fetch_bybit_quote(
        self,
        client: AsyncClient,
        asset: CryptoAsset,
    ) -> Decimal | None:
        response = await client.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "spot", "symbol": f"{asset.value}USDT"},
        )
        response.raise_for_status()
        payload = orjson.loads(response.content)
        result = payload.get("result") or {}
        data = result.get("list") or []
        if not data:
            return None
        return self._optional_decimal(data[0].get("ask1Price") or data[0].get("lastPrice"))

    def _aggregate_market_quotes(
        self,
        quotes: Iterable[tuple[str, Decimal]],
    ) -> tuple[Decimal, tuple[str, ...]]:
        normalized = [(provider, price) for provider, price in quotes if price > 0]
        if not normalized:
            raise ValueError("No valid market quotes were collected")

        prices = [price for _, price in normalized]
        if len(prices) >= 3:
            median_price = self._median(prices)
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

    def _build_market_quote(
        self,
        *,
        price: Decimal,
        source: str,
        providers: Sequence[str],
    ) -> MarketQuoteSnapshot:
        quote_expires_at = self._quote_expires_at()
        return MarketQuoteSnapshot(
            price=price,
            source=source,
            provider_count=len(providers),
            providers=tuple(providers),
            quote_expires_at=quote_expires_at,
        )

    def _build_static_market_quote(self, *, price: Decimal) -> MarketQuoteSnapshot:
        return self._build_market_quote(
            price=price,
            source=STATIC_QUOTE_SOURCE,
            providers=(),
        )

    def _build_static_conversion(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> CurrencyConversionQuote:
        normalized_amount = self._normalize_amount(amount, currency)
        return CurrencyConversionQuote(
            amount=normalized_amount,
            currency=currency,
            quote_rate=Decimal("1"),
            quote_source=STATIC_QUOTE_SOURCE,
            quote_provider_count=0,
            quote_expires_at=self._quote_expires_at(),
        )

    @staticmethod
    def _quote_expires_at() -> str:
        return (
            (datetime_now() + timedelta(seconds=MARKET_QUOTE_TTL_SECONDS))
            .replace(microsecond=0)
            .isoformat()
        )

    @staticmethod
    def _quote_to_cache(snapshot: MarketQuoteSnapshot) -> CachedMarketQuote:
        return CachedMarketQuote(
            price=str(snapshot.price),
            source=snapshot.source,
            provider_count=snapshot.provider_count,
            providers=list(snapshot.providers),
            quote_expires_at=snapshot.quote_expires_at,
        )

    @staticmethod
    def _restore_quote_from_cache(cached: CachedMarketQuote) -> MarketQuoteSnapshot:
        return MarketQuoteSnapshot(
            price=Decimal(cached.price),
            source=cached.source,
            provider_count=cached.provider_count,
            providers=tuple(cached.providers),
            quote_expires_at=cached.quote_expires_at,
        )

    @staticmethod
    def _merge_sources(*quotes: MarketQuoteSnapshot) -> str:
        parts = [quote.source for quote in quotes if quote.source]
        return "+".join(parts) if parts else STATIC_QUOTE_SOURCE

    @staticmethod
    def _currency_to_asset(currency: Currency) -> CryptoAsset:
        try:
            return CryptoAsset(currency.value)
        except ValueError as exception:
            raise ValueError(
                f"Currency '{currency.value}' is not a market crypto asset"
            ) from exception

    @staticmethod
    def _median(values: Sequence[Decimal]) -> Decimal:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / Decimal("2")

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        return Decimal(str(value))

    @classmethod
    def _optional_decimal(cls, value: Any) -> Decimal | None:
        if value in (None, "", "0", 0):
            return None
        try:
            parsed = cls._to_decimal(value)
        except Exception:
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _normalize_amount(amount: Decimal, currency: Currency) -> Decimal:
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


__all__ = [
    "CurrencyConversionQuote",
    "MARKET_QUOTE_TTL_SECONDS",
    "MarketQuoteService",
    "MarketQuoteSnapshot",
    "SUPPORTED_MARKET_CURRENCIES",
]
