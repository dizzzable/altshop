import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { GatewaysController } from './gateways.controller';
import { GatewaysService } from './gateways.service';
import { PaymentGateway } from '../../entities/payment-gateway.entity';

@Module({
  imports: [TypeOrmModule.forFeature([PaymentGateway])],
  controllers: [GatewaysController],
  providers: [GatewaysService],
  exports: [GatewaysService],
})
export class GatewaysModule {}