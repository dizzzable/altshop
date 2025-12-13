import {
  Controller,
  Get,
  Patch,
  Param,
  Body,
  Query,
  UseGuards,
  ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { SubscriptionsService } from './subscriptions.service';
import { PaginationDto } from '../../common/dto/pagination.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { SubscriptionStatus } from '../../entities/subscription.entity';

@ApiTags('subscriptions')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('subscriptions')
export class SubscriptionsController {
  constructor(private readonly subscriptionsService: SubscriptionsService) {}

  @Get()
  @ApiOperation({ summary: 'Get all subscriptions' })
  @ApiQuery({ name: 'status', required: false, enum: SubscriptionStatus })
  async findAll(
    @Query() pagination: PaginationDto,
    @Query('status') status?: SubscriptionStatus,
  ) {
    return this.subscriptionsService.findAll(pagination, status);
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get subscription statistics' })
  async getStatistics() {
    return this.subscriptionsService.getStatistics();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get subscription by ID' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.subscriptionsService.findOne(id);
  }

  @Get('user/:telegramId')
  @ApiOperation({ summary: 'Get subscriptions by user Telegram ID' })
  async findByUser(@Param('telegramId') telegramId: string) {
    return this.subscriptionsService.findByUser(telegramId);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update subscription' })
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateData: any,
  ) {
    return this.subscriptionsService.update(id, updateData);
  }
}