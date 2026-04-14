from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Awaitable, Callable

import orjson
from httpx import AsyncClient, HTTPError, Timeout
from loguru import logger

from src.core.enums import CryptoAsset
from src.core.storage.keys import MarketAssetUsdQuoteKey, MarketUsdRubQuoteKey
from src.services.market_quote import (
    FIAT_QUOTE_SOURCE,
    MARKET_QUOTE_SOURCE,
    MARKET_QUOTE_TTL_SECONDS,
    PEGGED_ASSET_USD_PRICE,
    CachedMarketQuote,
    MarketQuoteSnapshot,
)

from .market_quote_values import (
    build_market_quote,
    build_static_market_quote,
    optional_decimal,
    quote_to_cache,
    restore_quote_from_cache,
    to_decimal,
)

if TYPE_CHECKING:
    from .market_quote import MarketQuoteService


ProviderFetcher = Callable[[AsyncClient, CryptoAsset], Awaitable[Decimal | None]]


async def get_asset_usd_quote(
    service: MarketQuoteService,
    asset: CryptoAsset,
) -> MarketQuoteSnapshot:
    if asset in {CryptoAsset.USDT, CryptoAsset.USDC}:
        return build_static_market_quote(price=PEGGED_ASSET_USD_PRICE)

    cache_key = MarketAssetUsdQuoteKey(asset=asset.value)
    cached = await service.redis_repository.get(cache_key, CachedMarketQuote)
    if cached:
        return restore_quote_from_cache(cached)

    quotes = await collect_asset_quotes(service, asset)
    aggregated_price, providers = service._aggregate_market_quotes(quotes)
    snapshot = build_market_quote(
        price=aggregated_price,
        source=MARKET_QUOTE_SOURCE,
        providers=providers,
    )
    await service.redis_repository.set(
        cache_key,
        quote_to_cache(snapshot),
        ex=MARKET_QUOTE_TTL_SECONDS,
    )
    return snapshot


async def get_usd_rub_quote(service: MarketQuoteService) -> MarketQuoteSnapshot:
    cache_key = MarketUsdRubQuoteKey()
    cached = await service.redis_repository.get(cache_key, CachedMarketQuote)
    if cached:
        return restore_quote_from_cache(cached)

    async with AsyncClient(timeout=Timeout(15.0)) as client:
        response = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        response.raise_for_status()
        payload = orjson.loads(response.content)

    usd_rate = to_decimal(payload["Valute"]["USD"]["Value"])
    snapshot = build_market_quote(
        price=usd_rate,
        source=FIAT_QUOTE_SOURCE,
        providers=("cbr",),
    )
    await service.redis_repository.set(
        cache_key,
        quote_to_cache(snapshot),
        ex=MARKET_QUOTE_TTL_SECONDS,
    )
    return snapshot


async def collect_asset_quotes(
    service: MarketQuoteService,
    asset: CryptoAsset,
) -> list[tuple[str, Decimal]]:
    providers: tuple[tuple[str, ProviderFetcher], ...] = (
        ("coinbase", service._fetch_coinbase_quote),
        ("binance", service._fetch_binance_quote),
        ("okx", service._fetch_okx_quote),
        ("bitget", service._fetch_bitget_quote),
        ("upbit", service._fetch_upbit_quote),
        ("gate", service._fetch_gate_quote),
        ("kucoin", service._fetch_kucoin_quote),
        ("mexc", service._fetch_mexc_quote),
        ("htx", service._fetch_htx_quote),
        ("bybit", service._fetch_bybit_quote),
    )

    async with AsyncClient(timeout=Timeout(12.0)) as client:
        tasks = [
            run_provider(provider, client, asset, fetcher)
            for provider, fetcher in providers
        ]
        results = await asyncio.gather(*tasks)

    return [result for result in results if result is not None]


async def run_provider(
    provider: str,
    client: AsyncClient,
    asset: CryptoAsset,
    fetcher: ProviderFetcher,
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


async def fetch_coinbase_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        f"https://api.exchange.coinbase.com/products/{asset.value}-USD/book",
        params={"level": 1},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    if not isinstance(payload, dict):
        return None
    ask = payload.get("asks", [[None]])[0][0]
    return optional_decimal(ask)


async def fetch_binance_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.binance.com/api/v3/ticker/bookTicker",
        params={"symbol": f"{asset.value}USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    return optional_decimal(payload.get("askPrice"))


async def fetch_okx_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://www.okx.com/api/v5/market/ticker",
        params={"instId": f"{asset.value}-USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    data = payload.get("data") or []
    if not data:
        return None
    return optional_decimal(data[0].get("askPx"))


async def fetch_bitget_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.bitget.com/api/v2/spot/market/tickers",
        params={"symbol": f"{asset.value}USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    data = payload.get("data") or []
    if not data:
        return None
    return optional_decimal(data[0].get("askPr"))


async def fetch_upbit_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
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
    return optional_decimal(payload[0].get("trade_price"))


async def fetch_gate_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.gateio.ws/api/v4/spot/tickers",
        params={"currency_pair": f"{asset.value}_USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    if not isinstance(payload, list) or not payload:
        return None
    return optional_decimal(payload[0].get("lowest_ask") or payload[0].get("last"))


async def fetch_kucoin_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.kucoin.com/api/v1/market/orderbook/level1",
        params={"symbol": f"{asset.value}-USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    data = payload.get("data") or {}
    return optional_decimal(data.get("bestAsk") or data.get("price"))


async def fetch_mexc_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.mexc.com/api/v3/ticker/bookTicker",
        params={"symbol": f"{asset.value}USDT"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    return optional_decimal(payload.get("askPrice"))


async def fetch_htx_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
    response = await client.get(
        "https://api.huobi.pro/market/detail/merged",
        params={"symbol": f"{asset.value.lower()}usdt"},
    )
    response.raise_for_status()
    payload = orjson.loads(response.content)
    tick = payload.get("tick") or {}
    ask = tick.get("ask")
    if isinstance(ask, list) and ask:
        return optional_decimal(ask[0])
    return optional_decimal(tick.get("close"))


async def fetch_bybit_quote(client: AsyncClient, asset: CryptoAsset) -> Decimal | None:
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
    return optional_decimal(data[0].get("ask1Price") or data[0].get("lastPrice"))
