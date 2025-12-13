import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Body,
  Query,
  UseGuards,
  ParseIntPipe,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { BroadcastService, CreateBroadcastDto } from './broadcast.service';
import { BroadcastAudience } from '../../entities/broadcast.entity';

@Controller('broadcast')
@UseGuards(JwtAuthGuard)
export class BroadcastController {
  constructor(private readonly broadcastService: BroadcastService) {}

  @Get()
  async findAll(
    @Query('page') page = 1,
    @Query('limit') limit = 20,
  ) {
    return this.broadcastService.findAll(+page, +limit);
  }

  @Get('stats')
  async getStats() {
    return this.broadcastService.getStats();
  }

  @Get('audience-count')
  async getAudienceCount(
    @Query('audience') audience: BroadcastAudience,
    @Query('planId') planId?: string,
  ) {
    const count = await this.broadcastService.getAudienceCount(
      audience,
      planId ? parseInt(planId, 10) : undefined,
    );
    return { count };
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.broadcastService.findOne(id);
  }

  @Post()
  async create(@Body() dto: CreateBroadcastDto) {
    return this.broadcastService.create(dto);
  }

  @Post(':id/cancel')
  async cancel(@Param('id', ParseIntPipe) id: number) {
    return this.broadcastService.cancel(id);
  }

  @Delete(':id')
  async delete(@Param('id', ParseIntPipe) id: number) {
    return this.broadcastService.delete(id);
  }
}