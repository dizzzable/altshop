import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from './modules/auth/auth.module';
import { UsersModule } from './modules/users/users.module';
import { PlansModule } from './modules/plans/plans.module';
import { SettingsModule } from './modules/settings/settings.module';
import { PromocodesModule } from './modules/promocodes/promocodes.module';
import { SubscriptionsModule } from './modules/subscriptions/subscriptions.module';
import { TransactionsModule } from './modules/transactions/transactions.module';
import { DashboardModule } from './modules/dashboard/dashboard.module';
import { BroadcastModule } from './modules/broadcast/broadcast.module';
import { GatewaysModule } from './modules/gateways/gateways.module';
import { BackupModule } from './modules/backup/backup.module';
import { BotButtonsModule } from './modules/bot-buttons/bot-buttons.module';
import { BotAdminsModule } from './modules/bot-admins/bot-admins.module';
import { BannersModule } from './modules/banners/banners.module';
import { AuditModule } from './modules/audit/audit.module';
import { RemnawaveModule } from './modules/remnawave/remnawave.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '../../.env',
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: 'postgres',
        host: configService.get('DATABASE_HOST', 'altshop-db'),
        port: configService.get<number>('DATABASE_PORT', 5432),
        username: configService.get('DATABASE_USER', 'altshop'),
        password: configService.get('DATABASE_PASSWORD'),
        database: configService.get('DATABASE_NAME', 'altshop'),
        autoLoadEntities: true,
        synchronize: false, // Don't sync - use altshop's migrations
        logging: configService.get('NODE_ENV') === 'development',
      }),
      inject: [ConfigService],
    }),
    AuthModule,
    UsersModule,
    PlansModule,
    SettingsModule,
    PromocodesModule,
    SubscriptionsModule,
    TransactionsModule,
    DashboardModule,
    BroadcastModule,
    GatewaysModule,
    BackupModule,
    BotButtonsModule,
    BotAdminsModule,
    BannersModule,
    AuditModule,
    RemnawaveModule,
  ],
})
export class AppModule {}