import { IsBoolean, IsEnum, IsNumber, IsOptional, IsString, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  AccessMode,
  ReferralRewardType,
  ReferralLevel,
  ReferralAccrualStrategy,
  ReferralRewardStrategy,
} from '../../../entities/settings.entity';
import { Currency } from '../../../entities/plan.entity';

// DTO для настроек уведомлений пользователей
export class UserNotificationSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  expires_in_3_days?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  expires_in_2_days?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  expires_in_1_days?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  expired?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  limited?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  expired_1_day_ago?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  referral_attached?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  referral_reward?: boolean;
}

// DTO для настроек системных уведомлений
export class SystemNotificationSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  bot_lifetime?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  bot_update?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  user_registered?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  subscription?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  promocode_activated?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  trial_getted?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  node_status?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  user_first_connected?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  user_hwid?: boolean;
}

// DTO для настроек типа обмена баллов
export class ExchangeTypeSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  enabled?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  points_cost?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  min_points?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  max_points?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  gift_plan_id?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  gift_duration_days?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  max_discount_percent?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  max_traffic_gb?: number;
}

// DTO для настроек обмена баллов
export class PointsExchangeSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  exchange_enabled?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ExchangeTypeSettingsDto)
  subscription_days?: ExchangeTypeSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ExchangeTypeSettingsDto)
  gift_subscription?: ExchangeTypeSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ExchangeTypeSettingsDto)
  discount?: ExchangeTypeSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ExchangeTypeSettingsDto)
  traffic?: ExchangeTypeSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  points_per_day?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  min_exchange_points?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  max_exchange_points?: number;
}

// DTO для настроек награды реферальной программы
export class ReferralRewardSettingsDto {
  @ApiPropertyOptional({ enum: ReferralRewardType })
  @IsOptional()
  @IsEnum(ReferralRewardType)
  type?: ReferralRewardType;

  @ApiPropertyOptional({ enum: ReferralRewardStrategy })
  @IsOptional()
  @IsEnum(ReferralRewardStrategy)
  strategy?: ReferralRewardStrategy;

  @ApiPropertyOptional()
  @IsOptional()
  config?: Record<number, number>;
}

// DTO для настроек реферальной программы
export class ReferralSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  enable?: boolean;

  @ApiPropertyOptional({ enum: ReferralLevel })
  @IsOptional()
  @IsNumber()
  level?: ReferralLevel;

  @ApiPropertyOptional({ enum: ReferralAccrualStrategy })
  @IsOptional()
  @IsEnum(ReferralAccrualStrategy)
  accrual_strategy?: ReferralAccrualStrategy;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ReferralRewardSettingsDto)
  reward?: ReferralRewardSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  eligible_plan_ids?: number[];

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => PointsExchangeSettingsDto)
  points_exchange?: PointsExchangeSettingsDto;
}

// DTO для настроек партнерской программы
export class PartnerSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  enabled?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  level1_percent?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  level2_percent?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  level3_percent?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  tax_percent?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  yookassa_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  telegram_stars_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  cryptopay_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  heleket_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  pal24_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  wata_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  platega_commission?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  min_withdrawal_amount?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  auto_calculate_commission?: boolean;
}

// DTO для настроек мультиподписки
export class MultiSubscriptionSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  enabled?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  default_max_subscriptions?: number;
}

// DTO для обновления режима доступа
export class UpdateAccessModeDto {
  @ApiProperty({ enum: AccessMode })
  @IsEnum(AccessMode)
  accessMode: AccessMode;
}

// DTO для обновления условий доступа
export class UpdateAccessConditionsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  rulesRequired?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  channelRequired?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  rulesLink?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  channelId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  channelLink?: string;
}

// Основной DTO для обновления настроек
export class UpdateSettingsDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  rulesRequired?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  channelRequired?: boolean;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  rulesLink?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  channelId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  channelLink?: string;

  @ApiPropertyOptional({ enum: AccessMode })
  @IsOptional()
  @IsEnum(AccessMode)
  accessMode?: AccessMode;

  @ApiPropertyOptional({ enum: Currency })
  @IsOptional()
  @IsEnum(Currency)
  defaultCurrency?: Currency;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => UserNotificationSettingsDto)
  userNotifications?: UserNotificationSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => SystemNotificationSettingsDto)
  systemNotifications?: SystemNotificationSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => ReferralSettingsDto)
  referral?: ReferralSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => PartnerSettingsDto)
  partner?: PartnerSettingsDto;

  @ApiPropertyOptional()
  @IsOptional()
  @ValidateNested()
  @Type(() => MultiSubscriptionSettingsDto)
  multiSubscription?: MultiSubscriptionSettingsDto;
}