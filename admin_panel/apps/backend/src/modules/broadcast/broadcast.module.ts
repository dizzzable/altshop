import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BroadcastController } from './broadcast.controller';
import { BroadcastService } from './broadcast.service';
import { Broadcast, BroadcastMessage } from '../../entities/broadcast.entity';
import { User } from '../../entities/user.entity';

@Module({
  imports: [TypeOrmModule.forFeature([Broadcast, BroadcastMessage, User])],
  controllers: [BroadcastController],
  providers: [BroadcastService],
  exports: [BroadcastService],
})
export class BroadcastModule {}