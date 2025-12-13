import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance } from 'axios';

export interface SystemInfo {
  version: string;
  status: string;
  totalUsers: number;
  activeUsers: number;
  onlineUsers: number;
}

export interface RemnawaveUser {
  username: string;
  status: string;
  traffic: string;
  expiresAt: string;
}

export interface RemnawaveHost {
  id: string;
  address: string;
  port: number;
  remark: string;
}

export interface RemnawaveNode {
  id: string;
  name: string;
  address: string;
  status: string;
}

export interface RemnawaveInbound {
  tag: string;
  protocol: string;
  port: number;
  enabled: boolean;
}

@Injectable()
export class RemnawaveService {
  private readonly logger = new Logger(RemnawaveService.name);
  private client: AxiosInstance | null = null;
  private baseUrl: string;
  private apiToken: string;

  constructor(private configService: ConfigService) {
    // Используем те же переменные что и бот: REMNAWAVE_HOST, REMNAWAVE_PORT, REMNAWAVE_TOKEN
    const host = this.configService.get<string>('REMNAWAVE_HOST', '');
    const port = this.configService.get<string>('REMNAWAVE_PORT', '3000');
    this.apiToken = this.configService.get<string>('REMNAWAVE_TOKEN', '');
    const caddyToken = this.configService.get<string>('REMNAWAVE_CADDY_TOKEN', '');
    const cookie = this.configService.get<string>('REMNAWAVE_COOKIE', '');

    // Формируем URL из host и port (как делает бот)
    if (host) {
      // Если host уже содержит протокол, используем как есть
      if (host.startsWith('http://') || host.startsWith('https://')) {
        this.baseUrl = host;
      } else {
        // Иначе формируем URL (внутри Docker используем http)
        this.baseUrl = `http://${host}:${port}`;
      }
    } else {
      this.baseUrl = '';
    }

    if (this.baseUrl && this.apiToken) {
      const headers: Record<string, string> = {
        Authorization: `Bearer ${this.apiToken}`,
        'Content-Type': 'application/json',
      };

      // Добавляем Caddy токен если указан
      if (caddyToken) {
        headers['X-Api-Key'] = caddyToken;
      }

      // Добавляем cookie если указан
      if (cookie) {
        headers['Cookie'] = cookie;
      }

      this.client = axios.create({
        baseURL: this.baseUrl,
        headers,
        timeout: 10000,
      });
      this.logger.log(`RemnaWave client initialized: ${this.baseUrl}`);
    } else {
      this.logger.warn(
        `RemnaWave credentials not configured. Host: ${host || 'not set'}, Token: ${this.apiToken ? 'set' : 'not set'}`,
      );
    }
  }

  private isConfigured(): boolean {
    return this.client !== null;
  }

  async getSystemInfo(): Promise<SystemInfo> {
    if (!this.isConfigured()) {
      return {
        version: '-',
        status: 'Not configured',
        totalUsers: 0,
        activeUsers: 0,
        onlineUsers: 0,
      };
    }

    try {
      // Try to get system stats from RemnaWave API
      const response = await this.client!.get('/api/system/stats');
      const data = response.data;

      return {
        version: data.version || '-',
        status: 'online',
        totalUsers: data.totalUsers || 0,
        activeUsers: data.activeUsers || 0,
        onlineUsers: data.onlineUsers || 0,
      };
    } catch (error) {
      this.logger.error('Failed to get RemnaWave system info', error);
      return {
        version: '-',
        status: 'offline',
        totalUsers: 0,
        activeUsers: 0,
        onlineUsers: 0,
      };
    }
  }

  async getUsers(): Promise<RemnawaveUser[]> {
    if (!this.isConfigured()) {
      return [];
    }

    try {
      const response = await this.client!.get('/api/users');
      const users = response.data.users || response.data || [];

      return users.map((user: any) => ({
        username: user.username || user.name,
        status: user.status || (user.enable ? 'active' : 'disabled'),
        traffic: this.formatTraffic(user.usedTraffic || 0),
        expiresAt: user.expiryTime
          ? new Date(user.expiryTime * 1000).toLocaleDateString()
          : '-',
      }));
    } catch (error) {
      this.logger.error('Failed to get RemnaWave users', error);
      return [];
    }
  }

  async getHosts(): Promise<RemnawaveHost[]> {
    if (!this.isConfigured()) {
      return [];
    }

    try {
      const response = await this.client!.get('/api/hosts');
      const hosts = response.data.hosts || response.data || [];

      return hosts.map((host: any) => ({
        id: host.id || host.uuid,
        address: host.address || host.host,
        port: host.port,
        remark: host.remark || host.name || '',
      }));
    } catch (error) {
      this.logger.error('Failed to get RemnaWave hosts', error);
      return [];
    }
  }

  async getNodes(): Promise<RemnawaveNode[]> {
    if (!this.isConfigured()) {
      return [];
    }

    try {
      const response = await this.client!.get('/api/nodes');
      const nodes = response.data.nodes || response.data || [];

      return nodes.map((node: any) => ({
        id: node.id || node.uuid,
        name: node.name || node.remark,
        address: node.address || node.host,
        status: node.status || (node.online ? 'online' : 'offline'),
      }));
    } catch (error) {
      this.logger.error('Failed to get RemnaWave nodes', error);
      return [];
    }
  }

  async getInbounds(): Promise<RemnawaveInbound[]> {
    if (!this.isConfigured()) {
      return [];
    }

    try {
      const response = await this.client!.get('/api/inbounds');
      const inbounds = response.data.inbounds || response.data || [];

      return inbounds.map((inbound: any) => ({
        tag: inbound.tag || inbound.remark,
        protocol: inbound.protocol || inbound.type,
        port: inbound.port,
        enabled: inbound.enable !== false,
      }));
    } catch (error) {
      this.logger.error('Failed to get RemnaWave inbounds', error);
      return [];
    }
  }

  private formatTraffic(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}