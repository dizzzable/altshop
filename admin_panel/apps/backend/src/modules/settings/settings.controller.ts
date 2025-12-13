import { Controller, Get, Patch, Body, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { SettingsService } from './settings.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
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

@ApiTags('settings')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('settings')
export class SettingsController {
  constructor(private readonly settingsService: SettingsService) {}

  @Get()
  @ApiOperation({ summary: 'Get all bot settings' })
  async get() {
    return this.settingsService.get();
  }

  @Patch()
  @ApiOperation({ summary: 'Update bot settings' })
  async update(@Body() updateData: UpdateSettingsDto) {
    return this.settingsService.update(updateData);
  }

  // === Режим доступа ===

  @Patch('access/mode')
  @ApiOperation({ summary: 'Update access mode' })
  async updateAccessMode(@Body() data: UpdateAccessModeDto) {
    return this.settingsService.updateAccessMode(data);
  }

  @Patch('access/conditions')
  @ApiOperation({ summary: 'Update access conditions (rules, channel)' })
  async updateAccessConditions(@Body() data: UpdateAccessConditionsDto) {
    return this.settingsService.updateAccessConditions(data);
  }

  // === Уведомления ===

  @Patch('notifications/user')
  @ApiOperation({ summary: 'Update user notifications settings' })
  async updateUserNotifications(@Body() data: UserNotificationSettingsDto) {
    return this.settingsService.updateUserNotifications(data);
  }

  @Patch('notifications/system')
  @ApiOperation({ summary: 'Update system notifications settings' })
  async updateSystemNotifications(@Body() data: SystemNotificationSettingsDto) {
    return this.settingsService.updateSystemNotifications(data);
  }

  // === Реферальная программа ===

  @Patch('referral')
  @ApiOperation({ summary: 'Update referral program settings' })
  async updateReferral(@Body() data: ReferralSettingsDto) {
    return this.settingsService.updateReferral(data);
  }

  @Patch('referral/points-exchange')
  @ApiOperation({ summary: 'Update points exchange settings' })
  async updatePointsExchange(@Body() data: PointsExchangeSettingsDto) {
    return this.settingsService.updatePointsExchange(data);
  }

  // === Партнерская программа ===

  @Patch('partner')
  @ApiOperation({ summary: 'Update partner program settings' })
  async updatePartner(@Body() data: PartnerSettingsDto) {
    return this.settingsService.updatePartner(data);
  }

  // === Мультиподписка ===

  @Patch('multi-subscription')
  @ApiOperation({ summary: 'Update multi-subscription settings' })
  async updateMultiSubscription(@Body() data: MultiSubscriptionSettingsDto) {
    return this.settingsService.updateMultiSubscription(data);
  }
}