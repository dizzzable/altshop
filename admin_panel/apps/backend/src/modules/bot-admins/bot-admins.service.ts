import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { BotAdmin, AdminRole } from '../../entities/bot-admin.entity';
import { CreateBotAdminDto } from './dto/create-bot-admin.dto';
import { UpdateBotAdminDto } from './dto/update-bot-admin.dto';

@Injectable()
export class BotAdminsService {
  constructor(
    @InjectRepository(BotAdmin)
    private botAdminRepository: Repository<BotAdmin>,
  ) {}

  async findAll(): Promise<BotAdmin[]> {
    return this.botAdminRepository.find({
      order: { role: 'ASC', createdAt: 'DESC' },
    });
  }

  async findByRole(role: AdminRole): Promise<BotAdmin[]> {
    return this.botAdminRepository.find({
      where: { role },
      order: { createdAt: 'DESC' },
    });
  }

  async findOne(id: number): Promise<BotAdmin> {
    const admin = await this.botAdminRepository.findOne({ where: { id } });
    if (!admin) {
      throw new NotFoundException(`Admin with ID ${id} not found`);
    }
    return admin;
  }

  async findByTelegramId(telegramId: string): Promise<BotAdmin | null> {
    return this.botAdminRepository.findOne({ where: { telegramId } });
  }

  async create(createDto: CreateBotAdminDto): Promise<BotAdmin> {
    const existing = await this.findByTelegramId(createDto.telegramId);
    if (existing) {
      throw new ConflictException(`Admin with Telegram ID ${createDto.telegramId} already exists`);
    }
    const admin = this.botAdminRepository.create(createDto);
    return this.botAdminRepository.save(admin);
  }

  async update(id: number, updateDto: UpdateBotAdminDto): Promise<BotAdmin> {
    const admin = await this.findOne(id);
    Object.assign(admin, updateDto);
    return this.botAdminRepository.save(admin);
  }

  async remove(id: number): Promise<void> {
    const admin = await this.findOne(id);
    await this.botAdminRepository.remove(admin);
  }

  async toggleActive(id: number): Promise<BotAdmin> {
    const admin = await this.findOne(id);
    admin.isActive = !admin.isActive;
    return this.botAdminRepository.save(admin);
  }

  async updateLastActivity(telegramId: string): Promise<void> {
    await this.botAdminRepository.update(
      { telegramId },
      { lastActivity: new Date() },
    );
  }

  async updatePermissions(id: number, permissions: string[]): Promise<BotAdmin> {
    const admin = await this.findOne(id);
    admin.permissions = permissions;
    return this.botAdminRepository.save(admin);
  }

  async changeRole(id: number, role: AdminRole): Promise<BotAdmin> {
    const admin = await this.findOne(id);
    admin.role = role;
    return this.botAdminRepository.save(admin);
  }

  async getActiveAdmins(): Promise<BotAdmin[]> {
    return this.botAdminRepository.find({
      where: { isActive: true },
      order: { role: 'ASC' },
    });
  }
}