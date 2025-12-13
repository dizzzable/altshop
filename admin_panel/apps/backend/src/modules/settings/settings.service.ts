import { Injectable, NotFoundException, OnModuleInit } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import {
  Settings,
  AccessMode,
  UserNotificationSettings,
  SystemNotificationSettings,
  ReferralSettings,
  PartnerSettings,
  MultiSubscriptionSettings,
  DEFAULT_USER_NOTIFICATIONS,
  DEFAULT_SYSTEM_NOTIFICATIONS,
  DEFAULT_REFERRAL,
  DEFAULT_PARTNER,
  DEFAULT_MULTI_SUBSCRIPTION,
} from '../../entities/settings.entity';
import {
  UpdateSettingsDto,
  UpdateAccessModeDto,
  UpdateAccessConditionsDto,
  UserNotificationSettingsDto,
  SystemNotificationSettingsDto,
  ReferralSettingsDto,
  PartnerSettingsDto,
  MultiSubscriptionSettingsDto,
  PointsExchangeSettingsDto,
} from './dto/update-settings.dto';

@Injectable()
export class SettingsService implements OnModuleInit {
  constructor(
    @InjectRepository(Settings)
    private settingsRepository: Repository<Settings>,
  ) {}

  // Инициализация настроек при запуске модуля
  async onModuleInit(): Promise<void> {
    // Не создаём настройки автоматически - они должны быть созданы ботом
    // Admin panel только читает и редактирует существующие настройки
    await this.checkSettingsTable();
  }

  // Проверка наличия таблицы settings
  private async checkSettingsTable(): Promise<void> {
    try {
      // Используем raw query для проверки существования таблицы
      const result = await this.settingsRepository.query(`
        SELECT EXISTS (
          SELECT FROM information_schema.tables
          WHERE table_schema = 'public'
          AND table_name = 'settings'
        ) as exists
      `);
      
      const tableExists = result[0]?.exists === true;
      
      if (!tableExists) {
        console.log('⚠️ Settings table does not exist yet. It will be created by the bot on first run.');
        return;
      }

      const count = await this.settingsRepository.count();
      if (count === 0) {
        console.log('⚠️ Settings table is empty. Settings will be created by the bot on first run.');
      } else {
        console.log('✅ Settings found in database');
      }
    } catch (error) {
      // Ошибка подключения к БД или другая критическая ошибка
      console.log('⚠️ Could not check settings table:', (error as Error).message);
    }
  }

  // Получить настройки
  async get(): Promise<Settings> {
    const settings = await this.settingsRepository.findOne({ where: { id: 1 } });
    if (!settings) {
      throw new NotFoundException('Settings not found');
    }
    return settings;
  }

  // Обновить все настройки
  async update(updateData: UpdateSettingsDto): Promise<Settings> {
    const settings = await this.get();
    
    // Обновляем простые поля
    if (updateData.rulesRequired !== undefined) settings.rulesRequired = updateData.rulesRequired;
    if (updateData.channelRequired !== undefined) settings.channelRequired = updateData.channelRequired;
    if (updateData.rulesLink !== undefined) settings.rulesLink = updateData.rulesLink;
    if (updateData.channelId !== undefined) settings.channelId = updateData.channelId;
    if (updateData.channelLink !== undefined) settings.channelLink = updateData.channelLink;
    if (updateData.accessMode !== undefined) settings.accessMode = updateData.accessMode;
    if (updateData.defaultCurrency !== undefined) settings.defaultCurrency = updateData.defaultCurrency;
    
    // Обновляем вложенные объекты
    if (updateData.userNotifications) {
      settings.userNotifications = { ...settings.userNotifications, ...updateData.userNotifications };
    }
    if (updateData.systemNotifications) {
      settings.systemNotifications = { ...settings.systemNotifications, ...updateData.systemNotifications };
    }
    if (updateData.referral) {
      settings.referral = this.mergeReferralSettings(settings.referral, updateData.referral);
    }
    if (updateData.partner) {
      settings.partner = { ...settings.partner, ...updateData.partner };
    }
    if (updateData.multiSubscription) {
      settings.multiSubscription = { ...settings.multiSubscription, ...updateData.multiSubscription };
    }
    
    return this.settingsRepository.save(settings);
  }

  // Обновить режим доступа
  async updateAccessMode(data: UpdateAccessModeDto): Promise<Settings> {
    const settings = await this.get();
    settings.accessMode = data.accessMode;
    return this.settingsRepository.save(settings);
  }

  // Обновить условия доступа
  async updateAccessConditions(data: UpdateAccessConditionsDto): Promise<Settings> {
    const settings = await this.get();
    if (data.rulesRequired !== undefined) settings.rulesRequired = data.rulesRequired;
    if (data.channelRequired !== undefined) settings.channelRequired = data.channelRequired;
    if (data.rulesLink !== undefined) settings.rulesLink = data.rulesLink;
    if (data.channelId !== undefined) settings.channelId = data.channelId;
    if (data.channelLink !== undefined) settings.channelLink = data.channelLink;
    return this.settingsRepository.save(settings);
  }

  // Обновить уведомления пользователей
  async updateUserNotifications(data: UserNotificationSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.userNotifications = { ...settings.userNotifications, ...data };
    return this.settingsRepository.save(settings);
  }

  // Обновить системные уведомления
  async updateSystemNotifications(data: SystemNotificationSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.systemNotifications = { ...settings.systemNotifications, ...data };
    return this.settingsRepository.save(settings);
  }

  // Обновить настройки реферальной программы
  async updateReferral(data: ReferralSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.referral = this.mergeReferralSettings(settings.referral, data);
    return this.settingsRepository.save(settings);
  }

  // Обновить настройки обмена баллов
  async updatePointsExchange(data: PointsExchangeSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.referral = {
      ...settings.referral,
      points_exchange: this.mergePointsExchangeSettings(settings.referral.points_exchange, data),
    };
    return this.settingsRepository.save(settings);
  }

  // Обновить настройки партнерской программы
  async updatePartner(data: PartnerSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.partner = { ...settings.partner, ...data };
    return this.settingsRepository.save(settings);
  }

  // Обновить настройки мультиподписки
  async updateMultiSubscription(data: MultiSubscriptionSettingsDto): Promise<Settings> {
    const settings = await this.get();
    settings.multiSubscription = { ...settings.multiSubscription, ...data };
    return this.settingsRepository.save(settings);
  }

  // Вспомогательный метод для глубокого слияния настроек реферальной программы
  private mergeReferralSettings(current: ReferralSettings, update: ReferralSettingsDto): ReferralSettings {
    const result = { ...current };
    
    if (update.enable !== undefined) result.enable = update.enable;
    if (update.level !== undefined) result.level = update.level;
    if (update.accrual_strategy !== undefined) result.accrual_strategy = update.accrual_strategy;
    if (update.eligible_plan_ids !== undefined) result.eligible_plan_ids = update.eligible_plan_ids;
    
    if (update.reward) {
      result.reward = {
        ...result.reward,
        ...update.reward,
        config: update.reward.config ? { ...result.reward.config, ...update.reward.config } : result.reward.config,
      };
    }
    
    if (update.points_exchange) {
      result.points_exchange = this.mergePointsExchangeSettings(result.points_exchange, update.points_exchange);
    }
    
    return result;
  }

  // Вспомогательный метод для глубокого слияния настроек обмена баллов
  private mergePointsExchangeSettings(current: any, update: PointsExchangeSettingsDto): any {
    const result = { ...current };
    
    if (update.exchange_enabled !== undefined) result.exchange_enabled = update.exchange_enabled;
    if (update.points_per_day !== undefined) result.points_per_day = update.points_per_day;
    if (update.min_exchange_points !== undefined) result.min_exchange_points = update.min_exchange_points;
    if (update.max_exchange_points !== undefined) result.max_exchange_points = update.max_exchange_points;
    
    if (update.subscription_days) {
      result.subscription_days = { ...result.subscription_days, ...update.subscription_days };
    }
    if (update.gift_subscription) {
      result.gift_subscription = { ...result.gift_subscription, ...update.gift_subscription };
    }
    if (update.discount) {
      result.discount = { ...result.discount, ...update.discount };
    }
    if (update.traffic) {
      result.traffic = { ...result.traffic, ...update.traffic };
    }
    
    return result;
  }
}