import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { PaymentGateway, PaymentGatewayType, GatewaySettings } from '../../entities/payment-gateway.entity';
import { Currency } from '../../entities/plan.entity';

export interface UpdateGatewayDto {
  is_active?: boolean;
  order_index?: number;
  currency?: Currency;
  settings?: GatewaySettings;
}

export interface UpdateGatewaySettingsDto {
  api_key?: string;
  secret_key?: string;
  shop_id?: string;
  [key: string]: any;
}

@Injectable()
export class GatewaysService {
  constructor(
    @InjectRepository(PaymentGateway)
    private gatewayRepository: Repository<PaymentGateway>,
  ) {}

  async findAll(): Promise<PaymentGateway[]> {
    return this.gatewayRepository.find({
      order: { order_index: 'ASC' },
    });
  }

  async findOne(id: number): Promise<PaymentGateway | null> {
    return this.gatewayRepository.findOne({ where: { id } });
  }

  async findByType(type: PaymentGatewayType): Promise<PaymentGateway | null> {
    return this.gatewayRepository.findOne({ where: { type } });
  }

  async update(id: number, dto: UpdateGatewayDto): Promise<PaymentGateway> {
    const gateway = await this.findOne(id);
    if (!gateway) {
      throw new NotFoundException(`Gateway with id ${id} not found`);
    }

    Object.assign(gateway, dto);
    return this.gatewayRepository.save(gateway);
  }

  async updateSettings(id: number, settings: UpdateGatewaySettingsDto): Promise<PaymentGateway> {
    const gateway = await this.findOne(id);
    if (!gateway) {
      throw new NotFoundException(`Gateway with id ${id} not found`);
    }

    gateway.settings = {
      ...gateway.settings,
      ...settings,
      is_configure: this.checkIsConfigured(gateway.type, { ...gateway.settings, ...settings }),
    };

    return this.gatewayRepository.save(gateway);
  }

  async toggleActive(id: number): Promise<PaymentGateway> {
    const gateway = await this.findOne(id);
    if (!gateway) {
      throw new NotFoundException(`Gateway with id ${id} not found`);
    }

    gateway.is_active = !gateway.is_active;
    return this.gatewayRepository.save(gateway);
  }

  async moveUp(id: number): Promise<boolean> {
    const gateway = await this.findOne(id);
    if (!gateway) return false;

    const prevGateway = await this.gatewayRepository.findOne({
      where: {},
      order: { order_index: 'DESC' },
    });

    if (!prevGateway || prevGateway.order_index >= gateway.order_index) {
      // Find the gateway with the next lower order_index
      const gateways = await this.gatewayRepository.find({
        order: { order_index: 'ASC' },
      });

      const currentIndex = gateways.findIndex(g => g.id === id);
      if (currentIndex <= 0) return false;

      const prevGw = gateways[currentIndex - 1];
      const tempIndex = gateway.order_index;
      gateway.order_index = prevGw.order_index;
      prevGw.order_index = tempIndex;

      await this.gatewayRepository.save([gateway, prevGw]);
      return true;
    }

    return false;
  }

  async moveDown(id: number): Promise<boolean> {
    const gateways = await this.gatewayRepository.find({
      order: { order_index: 'ASC' },
    });

    const currentIndex = gateways.findIndex(g => g.id === id);
    if (currentIndex < 0 || currentIndex >= gateways.length - 1) return false;

    const gateway = gateways[currentIndex];
    const nextGw = gateways[currentIndex + 1];
    const tempIndex = gateway.order_index;
    gateway.order_index = nextGw.order_index;
    nextGw.order_index = tempIndex;

    await this.gatewayRepository.save([gateway, nextGw]);
    return true;
  }

  private checkIsConfigured(type: PaymentGatewayType, settings: GatewaySettings | null): boolean {
    if (!settings) return false;

    switch (type) {
      case PaymentGatewayType.TELEGRAM_STARS:
        return true; // No configuration needed
      case PaymentGatewayType.YOOKASSA:
        return !!(settings.shop_id && settings.secret_key);
      case PaymentGatewayType.YOOMONEY:
        return !!(settings.api_key);
      case PaymentGatewayType.CRYPTOMUS:
        return !!(settings.api_key && settings.shop_id);
      case PaymentGatewayType.HELEKET:
        return !!(settings.api_key);
      case PaymentGatewayType.CRYPTOPAY:
        return !!(settings.api_key);
      case PaymentGatewayType.ROBOKASSA:
        return !!(settings.shop_id && settings.secret_key);
      case PaymentGatewayType.PAL24:
        return !!(settings.api_key && settings.shop_id);
      case PaymentGatewayType.WATA:
        return !!(settings.api_key);
      case PaymentGatewayType.PLATEGA:
        return !!(settings.api_key && settings.shop_id);
      default:
        return false;
    }
  }

  getGatewayTypeLabel(type: PaymentGatewayType): string {
    const labels: Record<PaymentGatewayType, string> = {
      [PaymentGatewayType.TELEGRAM_STARS]: 'Telegram Stars',
      [PaymentGatewayType.YOOKASSA]: 'YooKassa',
      [PaymentGatewayType.YOOMONEY]: 'YooMoney',
      [PaymentGatewayType.CRYPTOMUS]: 'Cryptomus',
      [PaymentGatewayType.HELEKET]: 'Heleket',
      [PaymentGatewayType.CRYPTOPAY]: 'CryptoPay',
      [PaymentGatewayType.ROBOKASSA]: 'Robokassa',
      [PaymentGatewayType.PAL24]: 'Pal24',
      [PaymentGatewayType.WATA]: 'Wata',
      [PaymentGatewayType.PLATEGA]: 'Platega',
    };
    return labels[type] || type;
  }

  getCurrencySymbol(currency: Currency): string {
    const symbols: Record<Currency, string> = {
      [Currency.USD]: '$',
      [Currency.XTR]: '★',
      [Currency.RUB]: '₽',
      [Currency.EUR]: '€',
    };
    return symbols[currency] || currency;
  }
}