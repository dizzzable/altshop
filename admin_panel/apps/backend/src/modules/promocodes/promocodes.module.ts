import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { PromocodesService } from './promocodes.service';
import { PromocodesController } from './promocodes.controller';
import { Promocode, PromocodeActivation } from '../../entities/promocode.entity';

@Module({
  imports: [TypeOrmModule.forFeature([Promocode, PromocodeActivation])],
  controllers: [PromocodesController],
  providers: [PromocodesService],
  exports: [PromocodesService],
})
export class PromocodesModule {}