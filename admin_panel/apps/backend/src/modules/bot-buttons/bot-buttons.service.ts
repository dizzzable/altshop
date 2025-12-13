import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { BotButton, ButtonType } from '../../entities/bot-button.entity';
import { CreateBotButtonDto } from './dto/create-bot-button.dto';
import { UpdateBotButtonDto } from './dto/update-bot-button.dto';

@Injectable()
export class BotButtonsService {
  constructor(
    @InjectRepository(BotButton)
    private botButtonRepository: Repository<BotButton>,
  ) {}

  async findAll(): Promise<BotButton[]> {
    return this.botButtonRepository.find({
      order: { parentMenu: 'ASC', row: 'ASC', position: 'ASC' },
    });
  }

  async findByType(type: ButtonType): Promise<BotButton[]> {
    return this.botButtonRepository.find({
      where: { type },
      order: { row: 'ASC', position: 'ASC' },
    });
  }

  async findByParentMenu(parentMenu: string): Promise<BotButton[]> {
    return this.botButtonRepository.find({
      where: { parentMenu },
      order: { row: 'ASC', position: 'ASC' },
    });
  }

  async findOne(id: number): Promise<BotButton> {
    const button = await this.botButtonRepository.findOne({ where: { id } });
    if (!button) {
      throw new NotFoundException(`Button with ID ${id} not found`);
    }
    return button;
  }

  async create(createDto: CreateBotButtonDto): Promise<BotButton> {
    const button = this.botButtonRepository.create(createDto);
    return this.botButtonRepository.save(button);
  }

  async update(id: number, updateDto: UpdateBotButtonDto): Promise<BotButton> {
    const button = await this.findOne(id);
    Object.assign(button, updateDto);
    return this.botButtonRepository.save(button);
  }

  async remove(id: number): Promise<void> {
    const button = await this.findOne(id);
    await this.botButtonRepository.remove(button);
  }

  async toggleActive(id: number): Promise<BotButton> {
    const button = await this.findOne(id);
    button.isActive = !button.isActive;
    return this.botButtonRepository.save(button);
  }

  async reorder(buttons: { id: number; row: number; position: number }[]): Promise<void> {
    for (const item of buttons) {
      await this.botButtonRepository.update(item.id, {
        row: item.row,
        position: item.position,
      });
    }
  }

  async getMenuStructure(): Promise<Record<string, BotButton[]>> {
    const buttons = await this.findAll();
    const structure: Record<string, BotButton[]> = {};
    
    for (const button of buttons) {
      const menu = button.parentMenu || 'root';
      if (!structure[menu]) {
        structure[menu] = [];
      }
      structure[menu].push(button);
    }
    
    return structure;
  }
}