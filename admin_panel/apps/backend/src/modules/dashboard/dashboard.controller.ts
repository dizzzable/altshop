import { Controller, Get, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { DashboardService } from './dashboard.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('dashboard')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('dashboard')
export class DashboardController {
  constructor(private readonly dashboardService: DashboardService) {}

  @Get('overview')
  @ApiOperation({ summary: 'Get dashboard overview with all statistics' })
  async getOverview() {
    return this.dashboardService.getOverview();
  }

  @Get('statistics')
  @ApiOperation({ summary: 'Get detailed statistics for all sections' })
  async getStatistics() {
    return this.dashboardService.getDetailedStatistics();
  }

  @Get('recent')
  @ApiOperation({ summary: 'Get recent activity' })
  async getRecentActivity() {
    return this.dashboardService.getRecentActivity();
  }

  @Get('system-metrics')
  @ApiOperation({ summary: 'Get server system metrics (CPU, RAM, Disk)' })
  async getSystemMetrics() {
    return this.dashboardService.getSystemMetrics();
  }
}