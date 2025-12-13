import {
  Controller,
  Get,
  Param,
  Query,
  UseGuards,
  ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { TransactionsService } from './transactions.service';
import { PaginationDto } from '../../common/dto/pagination.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { TransactionStatus } from '../../entities/transaction.entity';

@ApiTags('transactions')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('transactions')
export class TransactionsController {
  constructor(private readonly transactionsService: TransactionsService) {}

  @Get()
  @ApiOperation({ summary: 'Get all transactions' })
  @ApiQuery({ name: 'status', required: false, enum: TransactionStatus })
  async findAll(
    @Query() pagination: PaginationDto,
    @Query('status') status?: TransactionStatus,
  ) {
    return this.transactionsService.findAll(pagination, status);
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get transaction statistics' })
  async getStatistics() {
    return this.transactionsService.getStatistics();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get transaction by ID' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.transactionsService.findOne(id);
  }

  @Get('user/:telegramId')
  @ApiOperation({ summary: 'Get transactions by user Telegram ID' })
  async findByUser(@Param('telegramId') telegramId: string) {
    return this.transactionsService.findByUser(telegramId);
  }
}