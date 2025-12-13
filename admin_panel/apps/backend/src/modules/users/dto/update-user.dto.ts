import { IsOptional, IsString, IsNumber, IsBoolean, IsEnum, Min, Max } from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';
import { UserRole, Locale } from '../../../entities/user.entity';

export class UpdateUserDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  name?: string;

  @ApiPropertyOptional({ enum: UserRole })
  @IsOptional()
  @IsEnum(UserRole)
  role?: UserRole;

  @ApiPropertyOptional({ enum: Locale })
  @IsOptional()
  @IsEnum(Locale)
  language?: Locale;

  @ApiPropertyOptional({ minimum: 0, maximum: 100 })
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(100)
  personalDiscount?: number;

  @ApiPropertyOptional({ minimum: 0, maximum: 100 })
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(100)
  purchaseDiscount?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  @Min(0)
  points?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsBoolean()
  isBlocked?: boolean;

  @ApiPropertyOptional({ description: 'Individual subscription limit. null = use global, -1 = unlimited' })
  @IsOptional()
  @IsNumber()
  maxSubscriptions?: number;
}