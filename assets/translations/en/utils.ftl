# Gateway types
gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] YooKassa
    [YOOMONEY] YooMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    [CRYPTOPAY] CryptoBot
    [PAL24] PayPalych
    [WATA] WATA
    [PLATEGA] Platega
    [ROBOKASSA] Robokassa
    [URLPAY] UrlPay
    *[OTHER] { $gateway_type }
}