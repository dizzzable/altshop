import {
  Controller,
  Get,
  Patch,
  Param,
  Body,
  UseGuards,
  ParseIntPipe,
  Post,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { PlansService } from './plans.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('plans')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('plans')
export class PlansController {
  constructor(private readonly plansService: PlansService) {}

  @Get()
  @ApiOperation({ summary: 'Get all plans' })
  async findAll() {
    return this.plansService.findAll();
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get plan statistics' })
  async getStatistics() {
    return this.plansService.getStatistics();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get plan by ID' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.plansService.findOne(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update plan' })
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateData: any,
  ) {
    return this.plansService.update(id, updateData);
  }

  @Post(':id/toggle')
  @ApiOperation({ summary: 'Toggle plan active status' })
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.plansService.toggleActive(id);
  }

  @Post('reorder')
  @ApiOperation({ summary: 'Reorder plans' })
  async reorder(@Body() body: { planIds: number[] }) {
    return this.plansService.reorder(body.planIds);
  }
}