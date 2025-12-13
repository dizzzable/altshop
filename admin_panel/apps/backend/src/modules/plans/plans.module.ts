import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { PlansService } from './plans.service';
import { PlansController } from './plans.controller';
import { Plan, PlanDuration, PlanPrice } from '../../entities/plan.entity';

@Module({
  imports: [TypeOrmModule.forFeature([Plan, PlanDuration, PlanPrice])],
  controllers: [PlansController],
  providers: [PlansService],
  exports: [PlansService],
})
export class PlansModule {}