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
import { BotButtonsService } from './bot-buttons.service';
import { CreateBotButtonDto } from './dto/create-bot-button.dto';
import { UpdateBotButtonDto } from './dto/update-bot-button.dto';
import { ButtonType } from '../../entities/bot-button.entity';

@Controller('bot-buttons')
@UseGuards(JwtAuthGuard)
export class BotButtonsController {
  constructor(private readonly botButtonsService: BotButtonsService) {}

  @Get()
  async findAll(@Query('type') type?: ButtonType, @Query('parentMenu') parentMenu?: string) {
    if (type) {
      return this.botButtonsService.findByType(type);
    }
    if (parentMenu) {
      return this.botButtonsService.findByParentMenu(parentMenu);
    }
    return this.botButtonsService.findAll();
  }

  @Get('structure')
  async getMenuStructure() {
    return this.botButtonsService.getMenuStructure();
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.botButtonsService.findOne(id);
  }

  @Post()
  async create(@Body() createDto: CreateBotButtonDto) {
    return this.botButtonsService.create(createDto);
  }

  @Put(':id')
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateDto: UpdateBotButtonDto,
  ) {
    return this.botButtonsService.update(id, updateDto);
  }

  @Put(':id/toggle')
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.botButtonsService.toggleActive(id);
  }

  @Post('reorder')
  async reorder(@Body() buttons: { id: number; row: number; position: number }[]) {
    await this.botButtonsService.reorder(buttons);
    return { success: true };
  }

  @Delete(':id')
  async remove(@Param('id', ParseIntPipe) id: number) {
    await this.botButtonsService.remove(id);
    return { success: true };
  }
}