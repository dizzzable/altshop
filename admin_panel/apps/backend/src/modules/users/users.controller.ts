import {
  Controller,
  Get,
  Patch,
  Param,
  Body,
  Query,
  UseGuards,
  ParseIntPipe,
  Post,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { UpdateUserDto } from './dto/update-user.dto';
import { PaginationDto } from '../../common/dto/pagination.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('users')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  @ApiOperation({ summary: 'Get all users with pagination' })
  @ApiQuery({ name: 'search', required: false })
  async findAll(
    @Query() pagination: PaginationDto,
    @Query('search') search?: string,
  ) {
    return this.usersService.findAll(pagination, search);
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get user statistics' })
  async getStatistics() {
    return this.usersService.getStatistics();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get user by ID' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.usersService.findOne(id);
  }

  @Get('telegram/:telegramId')
  @ApiOperation({ summary: 'Get user by Telegram ID' })
  async findByTelegramId(@Param('telegramId') telegramId: string) {
    return this.usersService.findByTelegramId(telegramId);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update user' })
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateUserDto: UpdateUserDto,
  ) {
    return this.usersService.update(id, updateUserDto);
  }

  @Post(':id/block')
  @ApiOperation({ summary: 'Block user' })
  async block(@Param('id', ParseIntPipe) id: number) {
    return this.usersService.block(id);
  }

  @Post(':id/unblock')
  @ApiOperation({ summary: 'Unblock user' })
  async unblock(@Param('id', ParseIntPipe) id: number) {
    return this.usersService.unblock(id);
  }
}