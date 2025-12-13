import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BotButton } from '../../entities/bot-button.entity';
import { BotButtonsController } from './bot-buttons.controller';
import { BotButtonsService } from './bot-buttons.service';

@Module({
  imports: [TypeOrmModule.forFeature([BotButton])],
  controllers: [BotButtonsController],
  providers: [BotButtonsService],
  exports: [BotButtonsService],
})
export class BotButtonsModule {}