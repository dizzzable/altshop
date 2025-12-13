import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Broadcast, BroadcastMessage, BroadcastStatus, BroadcastAudience } from '../../entities/broadcast.entity';
import { User } from '../../entities/user.entity';
import { v4 as uuidv4 } from 'uuid';

export interface CreateBroadcastDto {
  audience: BroadcastAudience;
  message: string;
  planId?: number;
  mediaType?: string;
  mediaFileId?: string;
  buttons?: Array<{ text: string; url: string }>;
}

export interface BroadcastStats {
  total: number;
  processing: number;
  completed: number;
  canceled: number;
  error: number;
}

@Injectable()
export class BroadcastService {
  constructor(
    @InjectRepository(Broadcast)
    private broadcastRepository: Repository<Broadcast>,
    @InjectRepository(BroadcastMessage)
    private messageRepository: Repository<BroadcastMessage>,
    @InjectRepository(User)
    private userRepository: Repository<User>,
  ) {}

  async findAll(page = 1, limit = 20): Promise<{ data: Broadcast[]; total: number; page: number; limit: number }> {
    const [data, total] = await this.broadcastRepository.findAndCount({
      order: { created_at: 'DESC' },
      skip: (page - 1) * limit,
      take: limit,
    });

    return { data, total, page, limit };
  }

  async findOne(id: number): Promise<Broadcast | null> {
    return this.broadcastRepository.findOne({
      where: { id },
    });
  }

  async getStats(): Promise<BroadcastStats> {
    const total = await this.broadcastRepository.count();
    const processing = await this.broadcastRepository.count({ where: { status: BroadcastStatus.PROCESSING } });
    const completed = await this.broadcastRepository.count({ where: { status: BroadcastStatus.COMPLETED } });
    const canceled = await this.broadcastRepository.count({ where: { status: BroadcastStatus.CANCELED } });
    const error = await this.broadcastRepository.count({ where: { status: BroadcastStatus.ERROR } });

    return { total, processing, completed, canceled, error };
  }

  async create(dto: CreateBroadcastDto): Promise<Broadcast> {
    // Get target users based on audience
    const targetUsers = await this.getTargetUsers(dto.audience, dto.planId);

    const broadcast = this.broadcastRepository.create({
      task_id: uuidv4(),
      status: BroadcastStatus.PROCESSING,
      audience: dto.audience,
      total_count: targetUsers.length,
      success_count: 0,
      failed_count: 0,
      payload: {
        message: dto.message,
        media_type: dto.mediaType,
        media_file_id: dto.mediaFileId,
        buttons: dto.buttons,
      },
    });

    const savedBroadcast = await this.broadcastRepository.save(broadcast);

    // Note: Actual message sending would be handled by the bot service
    // This just creates the broadcast record

    return savedBroadcast;
  }

  async cancel(id: number): Promise<Broadcast | null> {
    const broadcast = await this.findOne(id);
    if (!broadcast) return null;

    if (broadcast.status === BroadcastStatus.PROCESSING) {
      broadcast.status = BroadcastStatus.CANCELED;
      return this.broadcastRepository.save(broadcast);
    }

    return broadcast;
  }

  async delete(id: number): Promise<boolean> {
    const result = await this.broadcastRepository.delete(id);
    return (result.affected ?? 0) > 0;
  }

  private async getTargetUsers(audience: BroadcastAudience, planId?: number): Promise<User[]> {
    const queryBuilder = this.userRepository.createQueryBuilder('user');

    switch (audience) {
      case BroadcastAudience.ALL:
        // All users
        break;
      case BroadcastAudience.SUBSCRIBED:
        queryBuilder.innerJoin('subscriptions', 's', 's.user_telegram_id = user.telegram_id')
          .where('s.status = :status', { status: 'ACTIVE' });
        break;
      case BroadcastAudience.UNSUBSCRIBED:
        queryBuilder.leftJoin('subscriptions', 's', 's.user_telegram_id = user.telegram_id')
          .where('s.id IS NULL OR s.status != :status', { status: 'ACTIVE' });
        break;
      case BroadcastAudience.EXPIRED:
        queryBuilder.innerJoin('subscriptions', 's', 's.user_telegram_id = user.telegram_id')
          .where('s.status = :status', { status: 'EXPIRED' });
        break;
      case BroadcastAudience.TRIAL:
        queryBuilder.where('user.is_trial = :isTrial', { isTrial: true });
        break;
      case BroadcastAudience.PLAN:
        if (planId) {
          queryBuilder.innerJoin('subscriptions', 's', 's.user_telegram_id = user.telegram_id')
            .where('s.plan_id = :planId', { planId })
            .andWhere('s.status = :status', { status: 'ACTIVE' });
        }
        break;
    }

    return queryBuilder.getMany();
  }

  async getAudienceCount(audience: BroadcastAudience, planId?: number): Promise<number> {
    const users = await this.getTargetUsers(audience, planId);
    return users.length;
  }
}