import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Like, FindOptionsWhere } from 'typeorm';
import { User } from '../../entities/user.entity';
import { UpdateUserDto } from './dto/update-user.dto';
import { PaginationDto } from '../../common/dto/pagination.dto';

@Injectable()
export class UsersService {
  constructor(
    @InjectRepository(User)
    private userRepository: Repository<User>,
  ) {}

  async findAll(pagination: PaginationDto, search?: string) {
    const { page = 1, limit = 20 } = pagination;
    const skip = (page - 1) * limit;

    const where: FindOptionsWhere<User> = {};
    
    if (search) {
      // Search by telegram_id, username, or name
      return this.userRepository
        .createQueryBuilder('user')
        .where('user.telegram_id::text LIKE :search', { search: `%${search}%` })
        .orWhere('user.username ILIKE :search', { search: `%${search}%` })
        .orWhere('user.name ILIKE :search', { search: `%${search}%` })
        .skip(skip)
        .take(limit)
        .orderBy('user.created_at', 'DESC')
        .getManyAndCount()
        .then(([data, total]) => ({
          data,
          total,
          page,
          limit,
          totalPages: Math.ceil(total / limit),
        }));
    }

    const [data, total] = await this.userRepository.findAndCount({
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

  async findOne(id: number): Promise<User> {
    const user = await this.userRepository.findOne({
      where: { id },
    });

    if (!user) {
      throw new NotFoundException(`User with ID ${id} not found`);
    }

    return user;
  }

  async findByTelegramId(telegramId: string): Promise<User> {
    const user = await this.userRepository.findOne({
      where: { telegramId },
    });

    if (!user) {
      throw new NotFoundException(`User with Telegram ID ${telegramId} not found`);
    }

    return user;
  }

  async update(id: number, updateUserDto: UpdateUserDto): Promise<User> {
    const user = await this.findOne(id);
    
    Object.assign(user, updateUserDto);
    
    return this.userRepository.save(user);
  }

  async block(id: number): Promise<User> {
    const user = await this.findOne(id);
    user.isBlocked = true;
    return this.userRepository.save(user);
  }

  async unblock(id: number): Promise<User> {
    const user = await this.findOne(id);
    user.isBlocked = false;
    return this.userRepository.save(user);
  }

  async getStatistics() {
    const total = await this.userRepository.count();
    const blocked = await this.userRepository.count({ where: { isBlocked: true } });
    const botBlocked = await this.userRepository.count({ where: { isBotBlocked: true } });
    
    // Users registered today
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const registeredToday = await this.userRepository
      .createQueryBuilder('user')
      .where('user.created_at >= :today', { today })
      .getCount();

    // Users registered this week
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    
    const registeredThisWeek = await this.userRepository
      .createQueryBuilder('user')
      .where('user.created_at >= :weekAgo', { weekAgo })
      .getCount();

    return {
      total,
      blocked,
      botBlocked,
      active: total - blocked - botBlocked,
      registeredToday,
      registeredThisWeek,
    };
  }

  async getDetailedStatistics() {
    const total = await this.userRepository.count();
    const blocked = await this.userRepository.count({ where: { isBlocked: true } });
    const botBlocked = await this.userRepository.count({ where: { isBotBlocked: true } });
    
    // Time periods
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    
    const monthAgo = new Date();
    monthAgo.setDate(monthAgo.getDate() - 30);

    const newDaily = await this.userRepository
      .createQueryBuilder('user')
      .where('user.created_at >= :today', { today })
      .getCount();

    const newWeekly = await this.userRepository
      .createQueryBuilder('user')
      .where('user.created_at >= :weekAgo', { weekAgo })
      .getCount();

    const newMonthly = await this.userRepository
      .createQueryBuilder('user')
      .where('user.created_at >= :monthAgo', { monthAgo })
      .getCount();

    // Users with/without subscription (simplified - would need subscription relation)
    const withSubscription = 0; // TODO: implement with subscription relation
    const withoutSubscription = total;
    const withTrial = 0; // TODO: implement with subscription relation

    // Conversion rates (simplified)
    const conversionRate = 0; // TODO: calculate based on transactions
    const trialConversionRate = 0; // TODO: calculate based on trial conversions

    return {
      total,
      newDaily,
      newWeekly,
      newMonthly,
      withSubscription,
      withoutSubscription,
      withTrial,
      blocked,
      botBlocked,
      conversionRate,
      trialConversionRate,
    };
  }
}