import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';
import { Currency } from './plan.entity';

export enum PaymentGatewayType {
  TELEGRAM_STARS = 'TELEGRAM_STARS',
  YOOKASSA = 'YOOKASSA',
  YOOMONEY = 'YOOMONEY',
  CRYPTOMUS = 'CRYPTOMUS',
  HELEKET = 'HELEKET',
  CRYPTOPAY = 'CRYPTOPAY',
  ROBOKASSA = 'ROBOKASSA',
  PAL24 = 'PAL24',
  WATA = 'WATA',
  PLATEGA = 'PLATEGA',
}

export interface GatewaySettings {
  api_key?: string;
  secret_key?: string;
  shop_id?: string;
  is_configure?: boolean;
  [key: string]: any;
}

@Entity('payment_gateways')
export class PaymentGateway {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'int' })
  order_index: number;

  @Column({
    type: 'enum',
    enum: PaymentGatewayType,
    enumName: 'payment_gateway_type',
    unique: true,
  })
  type: PaymentGatewayType;

  @Column({
    type: 'enum',
    enum: Currency,
    enumName: 'currency',
  })
  currency: Currency;

  @Column({ type: 'boolean' })
  is_active: boolean;

  @Column({ type: 'jsonb', nullable: true })
  settings: GatewaySettings | null;
}