import { PartialType } from '@nestjs/mapped-types';
import { CreateBotButtonDto } from './create-bot-button.dto';

export class UpdateBotButtonDto extends PartialType(CreateBotButtonDto) {}