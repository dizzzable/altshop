import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Between, LessThan, MoreThan } from 'typeorm';
import { Subscription, SubscriptionStatus } from '../../entities/subscription.entity';
import { PaginationDto } from '../../common/dto/pagination.dto';

@Injectable()
export class SubscriptionsService {
  constructor(
    @InjectRepository(Subscription)
    private subscriptionRepository: Repository<Subscription>,
  ) {}

  async findAll(pagination: PaginationDto, status?: SubscriptionStatus) {
    const { page = 1, limit = 20 } = pagination;
    const skip = (page - 1) * limit;

    const where: any = {};
    if (status) {
      where.status = status;
    }

    const [data, total] = await this.subscriptionRepository.findAndCount({
      where,
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

  async findOne(id: number): Promise<Subscription> {
    const subscription = await this.subscriptionRepository.findOne({ where: { id } });
    if (!subscription) {
      throw new NotFoundException(`Subscription with ID ${id} not found`);
    }
    return subscription;
  }

  async findByUser(userTelegramId: string) {
    return this.subscriptionRepository.find({
      where: { userTelegramId },
      order: { createdAt: 'DESC' },
    });
  }

  async update(id: number, updateData: Partial<Subscription>): Promise<Subscription> {
    const subscription = await this.findOne(id);
    Object.assign(subscription, updateData);
    return this.subscriptionRepository.save(subscription);
  }

  async getStatistics() {
    const total = await this.subscriptionRepository.count();
    const active = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.ACTIVE },
    });
    const expired = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.EXPIRED },
    });
    const disabled = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.DISABLED },
    });

    // Expiring soon (within 3 days)
    const threeDaysFromNow = new Date();
    threeDaysFromNow.setDate(threeDaysFromNow.getDate() + 3);
    
    const expiringSoon = await this.subscriptionRepository.count({
      where: {
        status: SubscriptionStatus.ACTIVE,
        expiresAt: Between(new Date(), threeDaysFromNow),
      },
    });

    return {
      total,
      active,
      expired,
      disabled,
      expiringSoon,
    };
  }

  async getDetailedStatistics() {
    const total = await this.subscriptionRepository.count();
    const active = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.ACTIVE },
    });
    const expired = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.EXPIRED },
    });
    const disabled = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.DISABLED },
    });
    const limited = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.LIMITED },
    });

    // Expiring soon (within 7 days)
    const sevenDaysFromNow = new Date();
    sevenDaysFromNow.setDate(sevenDaysFromNow.getDate() + 7);
    
    const expiringSoon = await this.subscriptionRepository.count({
      where: {
        status: SubscriptionStatus.ACTIVE,
        expiresAt: Between(new Date(), sevenDaysFromNow),
      },
    });

    // With traffic limit (trafficLimit > 0)
    const withTrafficLimit = await this.subscriptionRepository
      .createQueryBuilder('subscription')
      .where('subscription.status = :status', { status: SubscriptionStatus.ACTIVE })
      .andWhere('CAST(subscription.traffic_limit AS BIGINT) > 0')
      .getCount();

    // Auto-renew enabled
    const autoRenew = await this.subscriptionRepository.count({
      where: { status: SubscriptionStatus.ACTIVE, isAutoRenew: true },
    });

    return {
      total,
      active,
      expired,
      disabled,
      limited,
      expiringSoon,
      withTrafficLimit,
      autoRenew,
    };
  }
}