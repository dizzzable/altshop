import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Between } from 'typeorm';
import { Transaction, TransactionStatus } from '../../entities/transaction.entity';
import { PaginationDto } from '../../common/dto/pagination.dto';

@Injectable()
export class TransactionsService {
  constructor(
    @InjectRepository(Transaction)
    private transactionRepository: Repository<Transaction>,
  ) {}

  async findAll(pagination: PaginationDto, status?: TransactionStatus) {
    const { page = 1, limit = 20 } = pagination;
    const skip = (page - 1) * limit;

    const where: any = {};
    if (status) {
      where.status = status;
    }

    const [data, total] = await this.transactionRepository.findAndCount({
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

  async findOne(id: number): Promise<Transaction> {
    const transaction = await this.transactionRepository.findOne({ where: { id } });
    if (!transaction) {
      throw new NotFoundException(`Transaction with ID ${id} not found`);
    }
    return transaction;
  }

  async findByUser(userTelegramId: string) {
    return this.transactionRepository.find({
      where: { userTelegramId },
      order: { createdAt: 'DESC' },
    });
  }

  async getStatistics() {
    const total = await this.transactionRepository.count();
    const completed = await this.transactionRepository.count({
      where: { status: TransactionStatus.COMPLETED },
    });
    const pending = await this.transactionRepository.count({
      where: { status: TransactionStatus.PENDING },
    });
    const failed = await this.transactionRepository.count({
      where: { status: TransactionStatus.FAILED },
    });

    // Revenue calculation
    const revenueResult = await this.transactionRepository
      .createQueryBuilder('transaction')
      .select('SUM(transaction.amount)', 'total')
      .addSelect('transaction.currency', 'currency')
      .where('transaction.status = :status', { status: TransactionStatus.COMPLETED })
      .groupBy('transaction.currency')
      .getRawMany();

    // Today's transactions
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const todayCount = await this.transactionRepository.count({
      where: {
        createdAt: Between(today, tomorrow),
        status: TransactionStatus.COMPLETED,
      },
    });

    const todayRevenueResult = await this.transactionRepository
      .createQueryBuilder('transaction')
      .select('SUM(transaction.amount)', 'total')
      .addSelect('transaction.currency', 'currency')
      .where('transaction.status = :status', { status: TransactionStatus.COMPLETED })
      .andWhere('transaction.created_at >= :today', { today })
      .andWhere('transaction.created_at < :tomorrow', { tomorrow })
      .groupBy('transaction.currency')
      .getRawMany();

    return {
      total,
      completed,
      pending,
      failed,
      revenue: revenueResult,
      todayCount,
      todayRevenue: todayRevenueResult,
    };
  }

  async getDetailedStatistics() {
    const total = await this.transactionRepository.count();
    const completed = await this.transactionRepository.count({
      where: { status: TransactionStatus.COMPLETED },
    });
    const free = await this.transactionRepository.count({
      where: { amount: 0 },
    });

    // Group by gateway
    const byGateway = await this.transactionRepository
      .createQueryBuilder('transaction')
      .select('transaction.gateway_type', 'name')
      .addSelect('COUNT(*)', 'total')
      .addSelect('SUM(CASE WHEN transaction.status = :completed THEN transaction.amount ELSE 0 END)', 'income')
      .setParameter('completed', TransactionStatus.COMPLETED)
      .groupBy('transaction.gateway_type')
      .getRawMany();

    return {
      total,
      completed,
      free,
      byGateway: byGateway.map(g => ({
        name: g.name || 'Unknown',
        total: parseInt(g.total) || 0,
        income: parseFloat(g.income) || 0,
      })),
    };
  }
}