import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Body,
  Res,
  UseGuards,
  StreamableFile,
} from '@nestjs/common';
import { Response } from 'express';
import { createReadStream } from 'fs';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { BackupService } from './backup.service';

@Controller('backup')
@UseGuards(JwtAuthGuard)
export class BackupController {
  constructor(private readonly backupService: BackupService) {}

  @Get()
  async listBackups() {
    return this.backupService.listBackups();
  }

  @Post('create')
  async createBackup() {
    return this.backupService.createBackup();
  }

  @Post('restore')
  async restoreBackup(
    @Body() body: { filename: string; clearExisting?: boolean },
  ) {
    return this.backupService.restoreBackup(body.filename, body.clearExisting);
  }

  @Delete(':filename')
  async deleteBackup(@Param('filename') filename: string) {
    return this.backupService.deleteBackup(filename);
  }

  @Get('download/:filename')
  async downloadBackup(
    @Param('filename') filename: string,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile | null> {
    const backup = await this.backupService.downloadBackup(filename);
    
    if (!backup) {
      res.status(404).json({ message: 'Backup not found' });
      return null;
    }

    res.set({
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${backup.filename}"`,
    });

    const file = createReadStream(backup.path);
    return new StreamableFile(file);
  }
}