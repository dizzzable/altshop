import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Between, LessThanOrEqual, MoreThanOrEqual } from 'typeorm';
import { AuditLog, AuditAction, AuditEntity } from '../../entities/audit-log.entity';

export interface CreateAuditLogDto {
  action: AuditAction;
  entityType: AuditEntity;
  entityId?: string;
  adminId?: string;
  adminUsername?: string;
  oldValue?: Record<string, any>;
  newValue?: Record<string, any>;
  description?: string;
  ipAddress?: string;
  userAgent?: string;
}

export interface AuditLogFilter {
  action?: AuditAction;
  entityType?: AuditEntity;
  entityId?: string;
  adminId?: string;
  startDate?: Date;
  endDate?: Date;
  limit?: number;
  offset?: number;
}

@Injectable()
export class AuditService {
  constructor(
    @InjectRepository(AuditLog)
    private auditLogRepository: Repository<AuditLog>,
  ) {}

  async log(data: CreateAuditLogDto): Promise<AuditLog> {
    const log = this.auditLogRepository.create(data);
    return this.auditLogRepository.save(log);
  }

  async findAll(filter: AuditLogFilter = {}): Promise<{ data: AuditLog[]; total: number }> {
    const { action, entityType, entityId, adminId, startDate, endDate, limit = 50, offset = 0 } = filter;

    const where: any = {};

    if (action) {
      where.action = action;
    }

    if (entityType) {
      where.entityType = entityType;
    }

    if (entityId) {
      where.entityId = entityId;
    }

    if (adminId) {
      where.adminId = adminId;
    }

    if (startDate && endDate) {
      where.createdAt = Between(startDate, endDate);
    } else if (startDate) {
      where.createdAt = MoreThanOrEqual(startDate);
    } else if (endDate) {
      where.createdAt = LessThanOrEqual(endDate);
    }

    const [data, total] = await this.auditLogRepository.findAndCount({
      where,
      order: { createdAt: 'DESC' },
      take: limit,
      skip: offset,
    });

    return { data, total };
  }

  async findByEntity(entityType: AuditEntity, entityId: string): Promise<AuditLog[]> {
    return this.auditLogRepository.find({
      where: { entityType, entityId },
      order: { createdAt: 'DESC' },
    });
  }

  async findByAdmin(adminId: string, limit = 100): Promise<AuditLog[]> {
    return this.auditLogRepository.find({
      where: { adminId },
      order: { createdAt: 'DESC' },
      take: limit,
    });
  }

  async getRecentActivity(limit = 20): Promise<AuditLog[]> {
    return this.auditLogRepository.find({
      order: { createdAt: 'DESC' },
      take: limit,
    });
  }

  async getStatsByAction(startDate?: Date, endDate?: Date): Promise<Record<string, number>> {
    const query = this.auditLogRepository
      .createQueryBuilder('log')
      .select('log.action', 'action')
      .addSelect('COUNT(*)', 'count')
      .groupBy('log.action');

    if (startDate) {
      query.andWhere('log.createdAt >= :startDate', { startDate });
    }

    if (endDate) {
      query.andWhere('log.createdAt <= :endDate', { endDate });
    }

    const results = await query.getRawMany();
    const stats: Record<string, number> = {};

    for (const row of results) {
      stats[row.action] = parseInt(row.count, 10);
    }

    return stats;
  }

  async getStatsByEntity(startDate?: Date, endDate?: Date): Promise<Record<string, number>> {
    const query = this.auditLogRepository
      .createQueryBuilder('log')
      .select('log.entityType', 'entityType')
      .addSelect('COUNT(*)', 'count')
      .groupBy('log.entityType');

    if (startDate) {
      query.andWhere('log.createdAt >= :startDate', { startDate });
    }

    if (endDate) {
      query.andWhere('log.createdAt <= :endDate', { endDate });
    }

    const results = await query.getRawMany();
    const stats: Record<string, number> = {};

    for (const row of results) {
      stats[row.entityType] = parseInt(row.count, 10);
    }

    return stats;
  }

  async cleanup(olderThan: Date): Promise<number> {
    const result = await this.auditLogRepository
      .createQueryBuilder()
      .delete()
      .where('createdAt < :olderThan', { olderThan })
      .execute();

    return result.affected || 0;
  }
}