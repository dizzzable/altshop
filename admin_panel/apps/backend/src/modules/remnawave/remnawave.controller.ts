import { Controller, Get, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import {
  RemnawaveService,
  SystemInfo,
  RemnawaveUser,
  RemnawaveHost,
  RemnawaveNode,
  RemnawaveInbound,
} from './remnawave.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('remnawave')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('remnawave')
export class RemnawaveController {
  constructor(private readonly remnawaveService: RemnawaveService) {}

  @Get('system')
  @ApiOperation({ summary: 'Get RemnaWave system info' })
  async getSystemInfo(): Promise<SystemInfo> {
    return this.remnawaveService.getSystemInfo();
  }

  @Get('users')
  @ApiOperation({ summary: 'Get RemnaWave users' })
  async getUsers(): Promise<RemnawaveUser[]> {
    return this.remnawaveService.getUsers();
  }

  @Get('hosts')
  @ApiOperation({ summary: 'Get RemnaWave hosts' })
  async getHosts(): Promise<RemnawaveHost[]> {
    return this.remnawaveService.getHosts();
  }

  @Get('nodes')
  @ApiOperation({ summary: 'Get RemnaWave nodes' })
  async getNodes(): Promise<RemnawaveNode[]> {
    return this.remnawaveService.getNodes();
  }

  @Get('inbounds')
  @ApiOperation({ summary: 'Get RemnaWave inbounds' })
  async getInbounds(): Promise<RemnawaveInbound[]> {
    return this.remnawaveService.getInbounds();
  }
}