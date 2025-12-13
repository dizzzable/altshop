import { Module } from '@nestjs/common';
import { DashboardService } from './dashboard.service';
import { DashboardController } from './dashboard.controller';
import { UsersModule } from '../users/users.module';
import { PlansModule } from '../plans/plans.module';
import { SubscriptionsModule } from '../subscriptions/subscriptions.module';
import { TransactionsModule } from '../transactions/transactions.module';
import { PromocodesModule } from '../promocodes/promocodes.module';

@Module({
  imports: [
    UsersModule,
    PlansModule,
    SubscriptionsModule,
    TransactionsModule,
    PromocodesModule,
  ],
  controllers: [DashboardController],
  providers: [DashboardService],
})
export class DashboardModule {}