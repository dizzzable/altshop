import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Plan, PlanDuration, PlanPrice } from '../../entities/plan.entity';

@Injectable()
export class PlansService {
  constructor(
    @InjectRepository(Plan)
    private planRepository: Repository<Plan>,
    @InjectRepository(PlanDuration)
    private durationRepository: Repository<PlanDuration>,
    @InjectRepository(PlanPrice)
    private priceRepository: Repository<PlanPrice>,
  ) {}

  async findAll() {
    return this.planRepository.find({
      relations: ['durations', 'durations.prices'],
      order: { orderIndex: 'ASC' },
    });
  }

  async findOne(id: number): Promise<Plan> {
    const plan = await this.planRepository.findOne({
      where: { id },
      relations: ['durations', 'durations.prices'],
    });

    if (!plan) {
      throw new NotFoundException(`Plan with ID ${id} not found`);
    }

    return plan;
  }

  async update(id: number, updateData: Partial<Plan>): Promise<Plan> {
    const plan = await this.findOne(id);
    Object.assign(plan, updateData);
    return this.planRepository.save(plan);
  }

  async toggleActive(id: number): Promise<Plan> {
    const plan = await this.findOne(id);
    plan.isActive = !plan.isActive;
    return this.planRepository.save(plan);
  }

  async reorder(planIds: number[]): Promise<Plan[]> {
    const plans = await Promise.all(
      planIds.map(async (id, index) => {
        const plan = await this.findOne(id);
        plan.orderIndex = index;
        return this.planRepository.save(plan);
      }),
    );
    return plans;
  }

  async getStatistics() {
    const total = await this.planRepository.count();
    const active = await this.planRepository.count({ where: { isActive: true } });
    
    return {
      total,
      active,
      inactive: total - active,
    };
  }

  async getDetailedStatistics() {
    const total = await this.planRepository.count();
    const active = await this.planRepository.count({ where: { isActive: true } });
    
    // Get plans with durations
    const plans = await this.planRepository.find({
      relations: ['durations', 'durations.prices'],
    });

    // Calculate average price
    let totalPrices = 0;
    let priceCount = 0;
    for (const plan of plans) {
      for (const duration of plan.durations || []) {
        for (const price of duration.prices || []) {
          totalPrices += Number(price.price);
          priceCount++;
        }
      }
    }
    const averagePrice = priceCount > 0 ? Math.round(totalPrices / priceCount) : 0;

    // Count total durations
    const totalDurations = await this.durationRepository.count();

    return {
      total,
      active,
      inactive: total - active,
      totalDurations,
      averagePrice,
    };
  }
}