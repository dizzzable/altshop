import { IsString, IsEnum, IsOptional, IsBoolean, IsNumber, IsObject } from 'class-validator';
import { ButtonType, ButtonAction } from '../../../entities/bot-button.entity';

export class CreateBotButtonDto {
  @IsString()
  name: string;

  @IsString()
  text: string;

  @IsOptional()
  @IsString()
  textKey?: string;

  @IsOptional()
  @IsEnum(ButtonType)
  type?: ButtonType;

  @IsOptional()
  @IsEnum(ButtonAction)
  action?: ButtonAction;

  @IsOptional()
  @IsString()
  actionData?: string;

  @IsOptional()
  @IsString()
  parentMenu?: string;

  @IsOptional()
  @IsNumber()
  position?: number;

  @IsOptional()
  @IsNumber()
  row?: number;

  @IsOptional()
  @IsString()
  emoji?: string;

  @IsOptional()
  @IsBoolean()
  isActive?: boolean;

  @IsOptional()
  @IsBoolean()
  requiresAdmin?: boolean;

  @IsOptional()
  @IsBoolean()
  requiresSubscription?: boolean;

  @IsOptional()
  @IsObject()
  conditions?: Record<string, any>;
}