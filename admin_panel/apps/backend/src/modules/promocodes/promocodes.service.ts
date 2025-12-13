import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Promocode, PromocodeActivation } from '../../entities/promocode.entity';
import { PaginationDto } from '../../common/dto/pagination.dto';

@Injectable()
export class PromocodesService {
  constructor(
    @InjectRepository(Promocode)
    private promocodeRepository: Repository<Promocode>,
    @InjectRepository(PromocodeActivation)
    private activationRepository: Repository<PromocodeActivation>,
  ) {}

  async findAll(pagination: PaginationDto) {
    const { page = 1, limit = 20 } = pagination;
    const skip = (page - 1) * limit;

    const [data, total] = await this.promocodeRepository.findAndCount({
      skip,
      take: limit,
      order: { createdAt: 'DESC' },
    });

    return {
      data,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async findOne(id: number): Promise<Promocode> {
    const promocode = await this.promocodeRepository.findOne({ where: { id } });
    if (!promocode) {
      throw new NotFoundException(`Promocode with ID ${id} not found`);
    }
    return promocode;
  }

  async create(createData: Partial<Promocode>): Promise<Promocode> {
    const existing = await this.promocodeRepository.findOne({
      where: { code: createData.code },
    });
    if (existing) {
      throw new ConflictException(`Promocode with code ${createData.code} already exists`);
    }
    const promocode = this.promocodeRepository.create(createData);
    return this.promocodeRepository.save(promocode);
  }

  async update(id: number, updateData: Partial<Promocode>): Promise<Promocode> {
    const promocode = await this.findOne(id);
    Object.assign(promocode, updateData);
    return this.promocodeRepository.save(promocode);
  }

  async delete(id: number): Promise<void> {
    const promocode = await this.findOne(id);
    await this.promocodeRepository.remove(promocode);
  }

  async toggleActive(id: number): Promise<Promocode> {
    const promocode = await this.findOne(id);
    promocode.isActive = !promocode.isActive;
    return this.promocodeRepository.save(promocode);
  }

  async getActivations(promocodeId: number) {
    return this.activationRepository.find({
      where: { promocodeId },
      order: { activatedAt: 'DESC' },
    });
  }

  async getStatistics() {
    const total = await this.promocodeRepository.count();
    const active = await this.promocodeRepository.count({ where: { isActive: true } });
    const totalActivations = await this.activationRepository.count();

    return {
      total,
      active,
      inactive: total - active,
      totalActivations,
    };
  }

  async getDetailedStatistics() {
    const total = await this.promocodeRepository.count();
    const active = await this.promocodeRepository.count({ where: { isActive: true } });
    const totalActivations = await this.activationRepository.count();

    // Get all promocodes for detailed analysis
    const promocodes = await this.promocodeRepository.find();

    // Count by type
    const byType: Record<string, number> = {};
    for (const promo of promocodes) {
      const type = promo.type || 'unknown';
      byType[type] = (byType[type] || 0) + 1;
    }

    // Count expired
    const now = new Date();
    const expired = promocodes.filter(p => p.validUntil && new Date(p.validUntil) < now).length;

    // Count fully used (max activations reached)
    const fullyUsed = promocodes.filter(p => p.maxActivations && p.currentActivations >= p.maxActivations).length;

    // Average discount
    const discounts = promocodes.filter(p => p.discount > 0).map(p => p.discount);
    const averageDiscount = discounts.length > 0
      ? Math.round(discounts.reduce((a, b) => a + b, 0) / discounts.length)
      : 0;

    return {
      total,
      active,
      inactive: total - active,
      totalActivations,
      expired,
      fullyUsed,
      averageDiscount,
      byType,
    };
  }
}