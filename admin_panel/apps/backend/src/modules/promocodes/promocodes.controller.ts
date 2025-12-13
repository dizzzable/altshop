import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Body,
  Query,
  UseGuards,
  ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { PromocodesService } from './promocodes.service';
import { PaginationDto } from '../../common/dto/pagination.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('promocodes')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('promocodes')
export class PromocodesController {
  constructor(private readonly promocodesService: PromocodesService) {}

  @Get()
  @ApiOperation({ summary: 'Get all promocodes' })
  async findAll(@Query() pagination: PaginationDto) {
    return this.promocodesService.findAll(pagination);
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get promocode statistics' })
  async getStatistics() {
    return this.promocodesService.getStatistics();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get promocode by ID' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.promocodesService.findOne(id);
  }

  @Get(':id/activations')
  @ApiOperation({ summary: 'Get promocode activations' })
  async getActivations(@Param('id', ParseIntPipe) id: number) {
    return this.promocodesService.getActivations(id);
  }

  @Post()
  @ApiOperation({ summary: 'Create promocode' })
  async create(@Body() createData: any) {
    return this.promocodesService.create(createData);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update promocode' })
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateData: any,
  ) {
    return this.promocodesService.update(id, updateData);
  }

  @Post(':id/toggle')
  @ApiOperation({ summary: 'Toggle promocode active status' })
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.promocodesService.toggleActive(id);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete promocode' })
  async delete(@Param('id', ParseIntPipe) id: number) {
    await this.promocodesService.delete(id);
    return { message: 'Promocode deleted successfully' };
  }
}