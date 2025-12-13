import { IsString, IsEnum, IsOptional, IsBoolean, IsArray } from 'class-validator';
import { AdminRole } from '../../../entities/bot-admin.entity';

export class CreateBotAdminDto {
  @IsString()
  telegramId: string;

  @IsOptional()
  @IsString()
  username?: string;

  @IsOptional()
  @IsString()
  firstName?: string;

  @IsOptional()
  @IsString()
  lastName?: string;

  @IsOptional()
  @IsEnum(AdminRole)
  role?: AdminRole;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  permissions?: string[];

  @IsOptional()
  @IsBoolean()
  isActive?: boolean;
}