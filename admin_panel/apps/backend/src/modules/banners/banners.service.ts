import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, LessThanOrEqual, MoreThanOrEqual, IsNull, Or } from 'typeorm';
import { Banner, BannerType } from '../../entities/banner.entity';
import { CreateBannerDto } from './dto/create-banner.dto';
import { UpdateBannerDto } from './dto/update-banner.dto';

@Injectable()
export class BannersService {
  constructor(
    @InjectRepository(Banner)
    private bannerRepository: Repository<Banner>,
  ) {}

  async findAll(): Promise<Banner[]> {
    return this.bannerRepository.find({
      order: { type: 'ASC', priority: 'DESC', createdAt: 'DESC' },
    });
  }

  async findByType(type: BannerType): Promise<Banner[]> {
    return this.bannerRepository.find({
      where: { type },
      order: { priority: 'DESC', createdAt: 'DESC' },
    });
  }

  async findByLocale(locale: string): Promise<Banner[]> {
    return this.bannerRepository.find({
      where: { locale },
      order: { type: 'ASC', priority: 'DESC' },
    });
  }

  async findOne(id: number): Promise<Banner> {
    const banner = await this.bannerRepository.findOne({ where: { id } });
    if (!banner) {
      throw new NotFoundException(`Banner with ID ${id} not found`);
    }
    return banner;
  }

  async create(createDto: CreateBannerDto): Promise<Banner> {
    const banner = this.bannerRepository.create(createDto);
    return this.bannerRepository.save(banner);
  }

  async update(id: number, updateDto: UpdateBannerDto): Promise<Banner> {
    const banner = await this.findOne(id);
    Object.assign(banner, updateDto);
    return this.bannerRepository.save(banner);
  }

  async remove(id: number): Promise<void> {
    const banner = await this.findOne(id);
    await this.bannerRepository.remove(banner);
  }

  async toggleActive(id: number): Promise<Banner> {
    const banner = await this.findOne(id);
    banner.isActive = !banner.isActive;
    return this.bannerRepository.save(banner);
  }

  async getActiveBanners(type?: BannerType, locale?: string): Promise<Banner[]> {
    const now = new Date();
    const where: any = {
      isActive: true,
    };

    if (type) {
      where.type = type;
    }

    if (locale) {
      where.locale = locale;
    }

    const banners = await this.bannerRepository.find({
      where,
      order: { priority: 'DESC' },
    });

    // Filter by date range
    return banners.filter((banner) => {
      const startOk = !banner.startDate || banner.startDate <= now;
      const endOk = !banner.endDate || banner.endDate >= now;
      return startOk && endOk;
    });
  }

  async updateFileId(id: number, fileId: string): Promise<Banner> {
    const banner = await this.findOne(id);
    banner.fileId = fileId;
    return this.bannerRepository.save(banner);
  }
}