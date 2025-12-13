import { PartialType } from '@nestjs/mapped-types';
import { CreateBotAdminDto } from './create-bot-admin.dto';

export class UpdateBotAdminDto extends PartialType(CreateBotAdminDto) {}