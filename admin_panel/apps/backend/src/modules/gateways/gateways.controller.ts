import {
  Controller,
  Get,
  Put,
  Patch,
  Post,
  Param,
  Body,
  UseGuards,
  ParseIntPipe,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { GatewaysService, UpdateGatewayDto, UpdateGatewaySettingsDto } from './gateways.service';

@Controller('gateways')
@UseGuards(JwtAuthGuard)
export class GatewaysController {
  constructor(private readonly gatewaysService: GatewaysService) {}

  @Get()
  async findAll() {
    return this.gatewaysService.findAll();
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.gatewaysService.findOne(id);
  }

  @Put(':id')
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateGatewayDto,
  ) {
    return this.gatewaysService.update(id, dto);
  }

  @Patch(':id/settings')
  async updateSettings(
    @Param('id', ParseIntPipe) id: number,
    @Body() settings: UpdateGatewaySettingsDto,
  ) {
    return this.gatewaysService.updateSettings(id, settings);
  }

  @Post(':id/toggle')
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.gatewaysService.toggleActive(id);
  }

  @Post(':id/move-up')
  async moveUp(@Param('id', ParseIntPipe) id: number) {
    const success = await this.gatewaysService.moveUp(id);
    return { success };
  }

  @Post(':id/move-down')
  async moveDown(@Param('id', ParseIntPipe) id: number) {
    const success = await this.gatewaysService.moveDown(id);
    return { success };
  }
}