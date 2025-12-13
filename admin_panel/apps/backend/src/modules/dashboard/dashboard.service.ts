import { Injectable } from '@nestjs/common';
import { UsersService } from '../users/users.service';
import { PlansService } from '../plans/plans.service';
import { SubscriptionsService } from '../subscriptions/subscriptions.service';
import { TransactionsService } from '../transactions/transactions.service';
import { PromocodesService } from '../promocodes/promocodes.service';
import * as os from 'os';
import { execSync } from 'child_process';

export interface CpuMetrics {
  usage: number;
  cores: number;
  model: string;
  speed: number;
}

export interface MemoryMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

export interface DiskMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

export interface SystemMetrics {
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  uptime: number;
  platform: string;
  hostname: string;
  timestamp: string;
}

@Injectable()
export class DashboardService {
  private previousCpuInfo: { idle: number; total: number } | null = null;

  constructor(
    private usersService: UsersService,
    private plansService: PlansService,
    private subscriptionsService: SubscriptionsService,
    private transactionsService: TransactionsService,
    private promocodesService: PromocodesService,
  ) {}

  async getOverview() {
    const [users, plans, subscriptions, transactions, promocodes] = await Promise.all([
      this.usersService.getStatistics(),
      this.plansService.getStatistics(),
      this.subscriptionsService.getStatistics(),
      this.transactionsService.getStatistics(),
      this.promocodesService.getStatistics(),
    ]);

    return {
      users,
      plans,
      subscriptions,
      transactions,
      promocodes,
      timestamp: new Date().toISOString(),
    };
  }

  async getDetailedStatistics() {
    const [users, transactions, subscriptions, plans, promocodes] = await Promise.all([
      this.usersService.getDetailedStatistics(),
      this.transactionsService.getDetailedStatistics(),
      this.subscriptionsService.getDetailedStatistics(),
      this.plansService.getDetailedStatistics(),
      this.promocodesService.getDetailedStatistics(),
    ]);

    return {
      users,
      transactions,
      subscriptions,
      plans,
      promocodes,
      timestamp: new Date().toISOString(),
    };
  }

  async getRecentActivity() {
    // Get recent users, transactions, etc.
    const [recentUsers, recentTransactions] = await Promise.all([
      this.usersService.findAll({ page: 1, limit: 5 }),
      this.transactionsService.findAll({ page: 1, limit: 10 }),
    ]);

    return {
      recentUsers: recentUsers.data,
      recentTransactions: recentTransactions.data,
    };
  }

  async getSystemMetrics(): Promise<SystemMetrics> {
    const cpuMetrics = this.getCpuMetrics();
    const memoryMetrics = this.getMemoryMetrics();
    const diskMetrics = await this.getDiskMetrics();

    return {
      cpu: cpuMetrics,
      memory: memoryMetrics,
      disk: diskMetrics,
      uptime: os.uptime(),
      platform: os.platform(),
      hostname: os.hostname(),
      timestamp: new Date().toISOString(),
    };
  }

  private getCpuMetrics(): CpuMetrics {
    const cpus = os.cpus();
    const cpuModel = cpus[0]?.model || 'Unknown';
    const cpuSpeed = cpus[0]?.speed || 0;
    const cpuCores = cpus.length;

    // Calculate CPU usage
    let totalIdle = 0;
    let totalTick = 0;

    for (const cpu of cpus) {
      for (const type in cpu.times) {
        totalTick += cpu.times[type as keyof typeof cpu.times];
      }
      totalIdle += cpu.times.idle;
    }

    let cpuUsage = 0;
    if (this.previousCpuInfo) {
      const idleDiff = totalIdle - this.previousCpuInfo.idle;
      const totalDiff = totalTick - this.previousCpuInfo.total;
      cpuUsage = totalDiff > 0 ? Math.round((1 - idleDiff / totalDiff) * 100) : 0;
    }

    this.previousCpuInfo = { idle: totalIdle, total: totalTick };

    return {
      usage: cpuUsage,
      cores: cpuCores,
      model: cpuModel,
      speed: cpuSpeed,
    };
  }

  private getMemoryMetrics(): MemoryMetrics {
    const totalMemory = os.totalmem();
    const freeMemory = os.freemem();
    const usedMemory = totalMemory - freeMemory;
    const usagePercent = Math.round((usedMemory / totalMemory) * 100);

    return {
      total: totalMemory,
      used: usedMemory,
      free: freeMemory,
      usagePercent,
    };
  }

  private async getDiskMetrics(): Promise<DiskMetrics> {
    try {
      const platform = os.platform();

      if (platform === 'win32') {
        // Windows
        const output = execSync('wmic logicaldisk get size,freespace,caption', {
          encoding: 'utf8',
        });
        const lines = output.trim().split('\n').slice(1);
        let totalDisk = 0;
        let freeDisk = 0;

        for (const line of lines) {
          const parts = line.trim().split(/\s+/);
          if (parts.length >= 3) {
            const free = parseInt(parts[1], 10);
            const total = parseInt(parts[2], 10);
            if (!isNaN(free) && !isNaN(total)) {
              freeDisk += free;
              totalDisk += total;
            }
          }
        }

        const usedDisk = totalDisk - freeDisk;
        const usagePercent = totalDisk > 0 ? Math.round((usedDisk / totalDisk) * 100) : 0;

        return {
          total: totalDisk,
          used: usedDisk,
          free: freeDisk,
          usagePercent,
        };
      } else {
        // Linux/Mac
        const output = execSync("df -B1 / | tail -1 | awk '{print $2,$3,$4}'", {
          encoding: 'utf8',
        });
        const [total, used, free] = output.trim().split(' ').map(Number);

        return {
          total: total || 0,
          used: used || 0,
          free: free || 0,
          usagePercent: total > 0 ? Math.round((used / total) * 100) : 0,
        };
      }
    } catch {
      // Fallback if disk info cannot be retrieved
      return {
        total: 0,
        used: 0,
        free: 0,
        usagePercent: 0,
      };
    }
  }
}