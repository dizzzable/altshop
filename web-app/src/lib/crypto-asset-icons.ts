import type { CryptoAsset } from '@/types'
import bitcoinIcon from '@/assets/currency/Bitcoin.svg'
import bnbIcon from '@/assets/currency/Bnb.svg'
import dashIcon from '@/assets/currency/dash.svg'
import ethIcon from '@/assets/currency/Eth.svg'
import ltcIcon from '@/assets/currency/Ltc.svg'
import moneroIcon from '@/assets/currency/monero.svg'
import solanaIcon from '@/assets/currency/Solana.svg'
import tonIcon from '@/assets/currency/Ton.svg'
import trxIcon from '@/assets/currency/Trx.svg'
import usdcIcon from '@/assets/currency/Usdc.svg'
import usdtIcon from '@/assets/currency/Usdt.svg'

const CRYPTO_ASSET_ICON_PATHS: Record<CryptoAsset, string> = {
  USDT: usdtIcon,
  TON: tonIcon,
  BTC: bitcoinIcon,
  ETH: ethIcon,
  LTC: ltcIcon,
  BNB: bnbIcon,
  DASH: dashIcon,
  SOL: solanaIcon,
  XMR: moneroIcon,
  USDC: usdcIcon,
  TRX: trxIcon,
}

const CRYPTO_ASSET_DISPLAY_NAMES: Record<CryptoAsset, string> = {
  USDT: 'USDT',
  TON: 'TON',
  BTC: 'Bitcoin',
  ETH: 'Ethereum',
  LTC: 'Litecoin',
  BNB: 'BNB',
  DASH: 'Dash',
  SOL: 'Solana',
  XMR: 'Monero',
  USDC: 'USDC',
  TRX: 'TRON',
}

export function getCryptoAssetIconPath(asset: CryptoAsset | string | undefined): string | null {
  if (!asset) {
    return null
  }

  return CRYPTO_ASSET_ICON_PATHS[asset as CryptoAsset] ?? null
}

export function getCryptoAssetDisplayName(asset: CryptoAsset | string | undefined): string {
  if (!asset) {
    return '-'
  }

  return CRYPTO_ASSET_DISPLAY_NAMES[asset as CryptoAsset] ?? asset
}
