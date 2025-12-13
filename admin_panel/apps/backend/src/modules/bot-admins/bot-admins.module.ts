import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BotAdmin } from '../../entities/bot-admin.entity';
import { BotAdminsController } from './bot-admins.controller';
import { BotAdminsService } from './bot-admins.service';

@Module({
  imports: [TypeOrmModule.forFeature([BotAdmin])],
  controllers: [BotAdminsController],
  providers: [BotAdminsService],
  exports: [BotAdminsService],
})
export class BotAdminsModule {}