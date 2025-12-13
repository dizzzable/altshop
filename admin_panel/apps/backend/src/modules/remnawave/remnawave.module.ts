import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { RemnawaveController } from './remnawave.controller';
import { RemnawaveService } from './remnawave.service';

@Module({
  imports: [ConfigModule],
  controllers: [RemnawaveController],
  providers: [RemnawaveService],
  exports: [RemnawaveService],
})
export class RemnawaveModule {}