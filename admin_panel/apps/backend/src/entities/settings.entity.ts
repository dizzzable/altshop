import { Entity, Column, PrimaryGeneratedColumn } from 'typeorm';
import { Currency } from './plan.entity';

// Режимы доступа к боту (соответствует боту)
export enum AccessMode {
  PUBLIC = 'PUBLIC',           // Доступ разрешен для всех
  INVITED = 'INVITED',         // Только приглашенные пользователи
  PURCHASE_BLOCKED = 'PURCHASE_BLOCKED', // Покупки запрещены
  REG_BLOCKED = 'REG_BLOCKED', // Регистрация запрещена
  RESTRICTED = 'RESTRICTED',   // Все действия полностью запрещены
}

// Типы наград реферальной программы
export enum ReferralRewardType {
  POINTS = 'POINTS',
  EXTRA_DAYS = 'EXTRA_DAYS',
}

// Уровни реферальной программы
export enum ReferralLevel {
  FIRST = 1,
  SECOND = 2,
  THIRD = 3,
}

// Стратегия начисления реферальных наград
export enum ReferralAccrualStrategy {
  ON_FIRST_PAYMENT = 'ON_FIRST_PAYMENT',
  ON_EACH_PAYMENT = 'ON_EACH_PAYMENT',
}

// Стратегия расчета награды
export enum ReferralRewardStrategy {
  AMOUNT = 'AMOUNT',   // Фиксированная сумма
  PERCENT = 'PERCENT', // Процент от платежа
}

// Типы обмена баллов
export enum PointsExchangeType {
  SUBSCRIPTION_DAYS = 'SUBSCRIPTION_DAYS', // Дни подписки
  GIFT_SUBSCRIPTION = 'GIFT_SUBSCRIPTION', // Подарочная подписка
  DISCOUNT = 'DISCOUNT',                   // Скидка
  TRAFFIC = 'TRAFFIC',                     // Дополнительный трафик
}

// Уровни партнерской программы
export enum PartnerLevel {
  LEVEL_1 = 1,
  LEVEL_2 = 2,
  LEVEL_3 = 3,
}

// Интерфейсы для JSONB полей

// Настройки уведомлений пользователей
export interface UserNotificationSettings {
  expires_in_3_days: boolean;
  expires_in_2_days: boolean;
  expires_in_1_days: boolean;
  expired: boolean;
  limited: boolean;
  expired_1_day_ago: boolean;
  referral_attached: boolean;
  referral_reward: boolean;
}

// Настройки системных уведомлений
export interface SystemNotificationSettings {
  bot_lifetime: boolean;
  bot_update: boolean;
  user_registered: boolean;
  subscription: boolean;
  promocode_activated: boolean;
  trial_getted: boolean;
  node_status: boolean;
  user_first_connected: boolean;
  user_hwid: boolean;
}

// Настройки типа обмена баллов
export interface ExchangeTypeSettings {
  enabled: boolean;
  points_cost: number;
  min_points: number;
  max_points: number;
  gift_plan_id?: number;
  gift_duration_days?: number;
  max_discount_percent?: number;
  max_traffic_gb?: number;
}

// Настройки обмена баллов
export interface PointsExchangeSettings {
  exchange_enabled: boolean;
  subscription_days: ExchangeTypeSettings;
  gift_subscription: ExchangeTypeSettings;
  discount: ExchangeTypeSettings;
  traffic: ExchangeTypeSettings;
  points_per_day: number;
  min_exchange_points: number;
  max_exchange_points: number;
}

// Настройки награды реферальной программы
export interface ReferralRewardSettings {
  type: ReferralRewardType;
  strategy: ReferralRewardStrategy;
  config: Record<number, number>; // level -> reward amount
}

// Настройки реферальной программы
export interface ReferralSettings {
  enable: boolean;
  level: ReferralLevel;
  accrual_strategy: ReferralAccrualStrategy;
  reward: ReferralRewardSettings;
  eligible_plan_ids: number[];
  points_exchange: PointsExchangeSettings;
}

// Настройки партнерской программы
export interface PartnerSettings {
  enabled: boolean;
  level1_percent: number;
  level2_percent: number;
  level3_percent: number;
  tax_percent: number;
  yookassa_commission: number;
  telegram_stars_commission: number;
  cryptopay_commission: number;
  heleket_commission: number;
  pal24_commission: number;
  wata_commission: number;
  platega_commission: number;
  min_withdrawal_amount: number;
  auto_calculate_commission: boolean;
}

// Настройки мультиподписки
export interface MultiSubscriptionSettings {
  enabled: boolean;
  default_max_subscriptions: number;
}

// Значения по умолчанию
export const DEFAULT_USER_NOTIFICATIONS: UserNotificationSettings = {
  expires_in_3_days: true,
  expires_in_2_days: true,
  expires_in_1_days: true,
  expired: true,
  limited: true,
  expired_1_day_ago: true,
  referral_attached: true,
  referral_reward: true,
};

export const DEFAULT_SYSTEM_NOTIFICATIONS: SystemNotificationSettings = {
  bot_lifetime: true,
  bot_update: true,
  user_registered: true,
  subscription: true,
  promocode_activated: true,
  trial_getted: true,
  node_status: true,
  user_first_connected: true,
  user_hwid: true,
};

export const DEFAULT_EXCHANGE_TYPE_SETTINGS: ExchangeTypeSettings = {
  enabled: false,
  points_cost: 1,
  min_points: 1,
  max_points: -1,
};

export const DEFAULT_POINTS_EXCHANGE: PointsExchangeSettings = {
  exchange_enabled: true,
  subscription_days: { ...DEFAULT_EXCHANGE_TYPE_SETTINGS, enabled: true },
  gift_subscription: { ...DEFAULT_EXCHANGE_TYPE_SETTINGS, points_cost: 30, min_points: 30, max_points: 30, gift_duration_days: 30 },
  discount: { ...DEFAULT_EXCHANGE_TYPE_SETTINGS, points_cost: 10, min_points: 10, max_points: 500, max_discount_percent: 50 },
  traffic: { ...DEFAULT_EXCHANGE_TYPE_SETTINGS, points_cost: 5, min_points: 5, max_traffic_gb: 100 },
  points_per_day: 1,
  min_exchange_points: 1,
  max_exchange_points: -1,
};

export const DEFAULT_REFERRAL: ReferralSettings = {
  enable: true,
  level: ReferralLevel.FIRST,
  accrual_strategy: ReferralAccrualStrategy.ON_FIRST_PAYMENT,
  reward: {
    type: ReferralRewardType.EXTRA_DAYS,
    strategy: ReferralRewardStrategy.AMOUNT,
    config: { [ReferralLevel.FIRST]: 5 },
  },
  eligible_plan_ids: [],
  points_exchange: DEFAULT_POINTS_EXCHANGE,
};

export const DEFAULT_PARTNER: PartnerSettings = {
  enabled: false,
  level1_percent: 10,
  level2_percent: 3,
  level3_percent: 1,
  tax_percent: 6,
  yookassa_commission: 3.5,
  telegram_stars_commission: 30,
  cryptopay_commission: 1,
  heleket_commission: 1,
  pal24_commission: 5,
  wata_commission: 3,
  platega_commission: 3.5,
  min_withdrawal_amount: 50000, // 500 рублей в копейках
  auto_calculate_commission: true,
};

export const DEFAULT_MULTI_SUBSCRIPTION: MultiSubscriptionSettings = {
  enabled: true,
  default_max_subscriptions: 5,
};

@Entity('settings')
export class Settings {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'rules_required', default: false })
  rulesRequired: boolean;

  @Column({ name: 'channel_required', default: false })
  channelRequired: boolean;

  @Column({ name: 'rules_link', default: 'https://telegram.org/tos/' })
  rulesLink: string;

  @Column({ name: 'channel_id', type: 'bigint', nullable: true })
  channelId: string;

  @Column({ name: 'channel_link', default: '@remna_shop' })
  channelLink: string;

  @Column({
    name: 'access_mode',
    type: 'varchar',
    default: AccessMode.PUBLIC,
  })
  accessMode: AccessMode;

  @Column({
    name: 'default_currency',
    type: 'varchar',
    default: Currency.RUB,
  })
  defaultCurrency: Currency;

  @Column({ name: 'user_notifications', type: 'jsonb', default: () => `'${JSON.stringify(DEFAULT_USER_NOTIFICATIONS)}'` })
  userNotifications: UserNotificationSettings;

  @Column({ name: 'system_notifications', type: 'jsonb', default: () => `'${JSON.stringify(DEFAULT_SYSTEM_NOTIFICATIONS)}'` })
  systemNotifications: SystemNotificationSettings;

  @Column({ type: 'jsonb', default: () => `'${JSON.stringify(DEFAULT_REFERRAL)}'` })
  referral: ReferralSettings;

  @Column({ type: 'jsonb', default: () => `'${JSON.stringify(DEFAULT_PARTNER)}'` })
  partner: PartnerSettings;

  @Column({ name: 'multi_subscription', type: 'jsonb', default: () => `'${JSON.stringify(DEFAULT_MULTI_SUBSCRIPTION)}'` })
  multiSubscription: MultiSubscriptionSettings;
}