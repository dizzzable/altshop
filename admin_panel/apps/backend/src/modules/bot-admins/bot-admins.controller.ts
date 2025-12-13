import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  Query,
  ParseIntPipe,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { BotAdminsService } from './bot-admins.service';
import { CreateBotAdminDto } from './dto/create-bot-admin.dto';
import { UpdateBotAdminDto } from './dto/update-bot-admin.dto';
import { AdminRole } from '../../entities/bot-admin.entity';

@Controller('bot-admins')
@UseGuards(JwtAuthGuard)
export class BotAdminsController {
  constructor(private readonly botAdminsService: BotAdminsService) {}

  @Get()
  async findAll(@Query('role') role?: AdminRole) {
    if (role) {
      return this.botAdminsService.findByRole(role);
    }
    return this.botAdminsService.findAll();
  }

  @Get('active')
  async getActiveAdmins() {
    return this.botAdminsService.getActiveAdmins();
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.botAdminsService.findOne(id);
  }

  @Get('telegram/:telegramId')
  async findByTelegramId(@Param('telegramId') telegramId: string) {
    return this.botAdminsService.findByTelegramId(telegramId);
  }

  @Post()
  async create(@Body() createDto: CreateBotAdminDto) {
    return this.botAdminsService.create(createDto);
  }

  @Put(':id')
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateDto: UpdateBotAdminDto,
  ) {
    return this.botAdminsService.update(id, updateDto);
  }

  @Put(':id/toggle')
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.botAdminsService.toggleActive(id);
  }

  @Put(':id/role')
  async changeRole(
    @Param('id', ParseIntPipe) id: number,
    @Body('role') role: AdminRole,
  ) {
    return this.botAdminsService.changeRole(id, role);
  }

  @Put(':id/permissions')
  async updatePermissions(
    @Param('id', ParseIntPipe) id: number,
    @Body('permissions') permissions: string[],
  ) {
    return this.botAdminsService.updatePermissions(id, permissions);
  }

  @Delete(':id')
  async remove(@Param('id', ParseIntPipe) id: number) {
    await this.botAdminsService.remove(id);
    return { success: true };
  }
}