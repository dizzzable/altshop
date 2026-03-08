from __future__ import annotations

from src.core.enums import CryptoAsset, PaymentGatewayType

_GATEWAY_PAYMENT_ASSETS: dict[PaymentGatewayType, tuple[CryptoAsset, ...]] = {
    PaymentGatewayType.CRYPTOMUS: (
        CryptoAsset.USDT,
        CryptoAsset.TON,
        CryptoAsset.BTC,
        CryptoAsset.ETH,
        CryptoAsset.LTC,
        CryptoAsset.BNB,
        CryptoAsset.DASH,
        CryptoAsset.SOL,
        CryptoAsset.XMR,
        CryptoAsset.USDC,
        CryptoAsset.TRX,
    ),
    PaymentGatewayType.HELEKET: (
        CryptoAsset.USDT,
        CryptoAsset.TON,
        CryptoAsset.BTC,
        CryptoAsset.ETH,
        CryptoAsset.LTC,
        CryptoAsset.BNB,
        CryptoAsset.DASH,
        CryptoAsset.XMR,
        CryptoAsset.USDC,
        CryptoAsset.TRX,
    ),
    PaymentGatewayType.CRYPTOPAY: (
        CryptoAsset.USDT,
        CryptoAsset.TON,
        CryptoAsset.BTC,
        CryptoAsset.ETH,
        CryptoAsset.LTC,
        CryptoAsset.BNB,
        CryptoAsset.USDC,
        CryptoAsset.TRX,
    ),
}


def get_supported_payment_assets(gateway_type: PaymentGatewayType) -> tuple[CryptoAsset, ...]:
    return _GATEWAY_PAYMENT_ASSETS.get(gateway_type, ())


def is_crypto_payment_gateway(gateway_type: PaymentGatewayType) -> bool:
    return gateway_type in _GATEWAY_PAYMENT_ASSETS


def get_default_payment_asset(gateway_type: PaymentGatewayType) -> CryptoAsset | None:
    supported_assets = get_supported_payment_assets(gateway_type)
    return supported_assets[0] if supported_assets else None
