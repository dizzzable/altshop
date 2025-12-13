import {
  Controller,
  Get,
  Query,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { AuditService, AuditLogFilter } from './audit.service';
import { AuditAction, AuditEntity } from '../../entities/audit-log.entity';

@Controller('audit')
@UseGuards(JwtAuthGuard)
export class AuditController {
  constructor(private readonly auditService: AuditService) {}

  @Get()
  async findAll(
    @Query('action') action?: AuditAction,
    @Query('entityType') entityType?: AuditEntity,
    @Query('entityId') entityId?: string,
    @Query('adminId') adminId?: string,
    @Query('startDate') startDate?: string,
    @Query('endDate') endDate?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    const filter: AuditLogFilter = {
      action,
      entityType,
      entityId,
      adminId,
      startDate: startDate ? new Date(startDate) : undefined,
      endDate: endDate ? new Date(endDate) : undefined,
      limit: limit ? parseInt(limit, 10) : 50,
      offset: offset ? parseInt(offset, 10) : 0,
    };

    return this.auditService.findAll(filter);
  }

  @Get('recent')
  async getRecentActivity(@Query('limit') limit?: string) {
    return this.auditService.getRecentActivity(limit ? parseInt(limit, 10) : 20);
  }

  @Get('entity/:entityType/:entityId')
  async findByEntity(
    @Query('entityType') entityType: AuditEntity,
    @Query('entityId') entityId: string,
  ) {
    return this.auditService.findByEntity(entityType, entityId);
  }

  @Get('admin/:adminId')
  async findByAdmin(
    @Query('adminId') adminId: string,
    @Query('limit') limit?: string,
  ) {
    return this.auditService.findByAdmin(adminId, limit ? parseInt(limit, 10) : 100);
  }

  @Get('stats/actions')
  async getStatsByAction(
    @Query('startDate') startDate?: string,
    @Query('endDate') endDate?: string,
  ) {
    return this.auditService.getStatsByAction(
      startDate ? new Date(startDate) : undefined,
      endDate ? new Date(endDate) : undefined,
    );
  }

  @Get('stats/entities')
  async getStatsByEntity(
    @Query('startDate') startDate?: string,
    @Query('endDate') endDate?: string,
  ) {
    return this.auditService.getStatsByEntity(
      startDate ? new Date(startDate) : undefined,
      endDate ? new Date(endDate) : undefined,
    );
  }
}