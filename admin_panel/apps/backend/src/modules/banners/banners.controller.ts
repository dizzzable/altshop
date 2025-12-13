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
import { BannersService } from './banners.service';
import { CreateBannerDto } from './dto/create-banner.dto';
import { UpdateBannerDto } from './dto/update-banner.dto';
import { BannerType } from '../../entities/banner.entity';

@Controller('banners')
@UseGuards(JwtAuthGuard)
export class BannersController {
  constructor(private readonly bannersService: BannersService) {}

  @Get()
  async findAll(
    @Query('type') type?: BannerType,
    @Query('locale') locale?: string,
  ) {
    if (type) {
      return this.bannersService.findByType(type);
    }
    if (locale) {
      return this.bannersService.findByLocale(locale);
    }
    return this.bannersService.findAll();
  }

  @Get('active')
  async getActiveBanners(
    @Query('type') type?: BannerType,
    @Query('locale') locale?: string,
  ) {
    return this.bannersService.getActiveBanners(type, locale);
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.bannersService.findOne(id);
  }

  @Post()
  async create(@Body() createDto: CreateBannerDto) {
    return this.bannersService.create(createDto);
  }

  @Put(':id')
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() updateDto: UpdateBannerDto,
  ) {
    return this.bannersService.update(id, updateDto);
  }

  @Put(':id/toggle')
  async toggleActive(@Param('id', ParseIntPipe) id: number) {
    return this.bannersService.toggleActive(id);
  }

  @Put(':id/file-id')
  async updateFileId(
    @Param('id', ParseIntPipe) id: number,
    @Body('fileId') fileId: string,
  ) {
    return this.bannersService.updateFileId(id, fileId);
  }

  @Delete(':id')
  async remove(@Param('id', ParseIntPipe) id: number) {
    await this.bannersService.remove(id);
    return { success: true };
  }
}