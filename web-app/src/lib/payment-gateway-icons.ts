import type { PaymentGatewayType } from '@/types'
import cloudPaymentsIcon from '@/assets/payment-gateways/CloudePayments.svg'
import cryptomusIcon from '@/assets/payment-gateways/Cryptomus.svg'
import cryptopayIcon from '@/assets/payment-gateways/Cryptopay.svg'
import heleketIcon from '@/assets/payment-gateways/Heleket.svg'
import mulenPayIcon from '@/assets/payment-gateways/MulenPay.svg'
import paypalychIcon from '@/assets/payment-gateways/Paypalych.svg'
import plategaIcon from '@/assets/payment-gateways/Platega.svg'
import robokassaIcon from '@/assets/payment-gateways/Robokassa.svg'
import stripeIcon from '@/assets/payment-gateways/Stripe.svg'
import tbankIcon from '@/assets/payment-gateways/tbank.svg'
import telegramStarsIcon from '@/assets/payment-gateways/TelegramStars.svg'
import wataIcon from '@/assets/payment-gateways/wata.svg'
import yookassaIcon from '@/assets/payment-gateways/Yookassa.svg'
import yoomoneyIcon from '@/assets/payment-gateways/Yoomoney.svg'

const PAYMENT_GATEWAY_ICON_PATHS: Partial<Record<PaymentGatewayType, string>> = {
  TELEGRAM_STARS: telegramStarsIcon,
  HELEKET: heleketIcon,
  PLATEGA: plategaIcon,
  PAL24: paypalychIcon,
  WATA: wataIcon,
  YOOKASSA: yookassaIcon,
  YOOMONEY: yoomoneyIcon,
  TBANK: tbankIcon,
  CRYPTOPAY: cryptopayIcon,
  CRYPTOMUS: cryptomusIcon,
  ROBOKASSA: robokassaIcon,
  STRIPE: stripeIcon,
  MULENPAY: mulenPayIcon,
  CLOUDPAYMENTS: cloudPaymentsIcon,
}

const PAYMENT_GATEWAY_DISPLAY_NAMES: Partial<Record<PaymentGatewayType, string>> = {
  TELEGRAM_STARS: 'Telegram Stars',
  YOOKASSA: 'YooKassa',
  YOOMONEY: 'YooMoney',
  TBANK: 'T-Bank',
  CRYPTOPAY: 'Crypto Pay',
  CRYPTOMUS: 'Cryptomus',
  HELEKET: 'Heleket',
  ROBOKASSA: 'Robokassa',
  STRIPE: 'Stripe',
  MULENPAY: 'MulenPay',
  CLOUDPAYMENTS: 'CloudPayments',
  PAL24: 'Pal24',
  WATA: 'WATA',
  PLATEGA: 'Platega',
}

export function getPaymentGatewayIconPath(gatewayType: string | undefined): string | null {
  if (!gatewayType) {
    return null
  }
  return PAYMENT_GATEWAY_ICON_PATHS[gatewayType as PaymentGatewayType] ?? null
}

export function getPaymentGatewayDisplayName(gatewayType: string | undefined): string {
  if (!gatewayType) {
    return '-'
  }

  return (
    PAYMENT_GATEWAY_DISPLAY_NAMES[gatewayType as PaymentGatewayType]
    ?? gatewayType.replaceAll('_', ' ')
  )
}
