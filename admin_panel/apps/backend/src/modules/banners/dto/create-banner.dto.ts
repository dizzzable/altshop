import { IsString, IsEnum, IsOptional, IsBoolean, IsNumber, IsDateString } from 'class-validator';
import { BannerType } from '../../../entities/banner.entity';

export class CreateBannerDto {
  @IsString()
  name: string;

  @IsOptional()
  @IsEnum(BannerType)
  type?: BannerType;

  @IsOptional()
  @IsString()
  filePath?: string;

  @IsOptional()
  @IsString()
  fileId?: string;

  @IsOptional()
  @IsString()
  locale?: string;

  @IsOptional()
  @IsBoolean()
  isActive?: boolean;

  @IsOptional()
  @IsNumber()
  priority?: number;

  @IsOptional()
  @IsDateString()
  startDate?: string;

  @IsOptional()
  @IsDateString()
  endDate?: string;
}