import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface BackupInfo {
  filename: string;
  size: number;
  createdAt: Date;
  path: string;
}

export interface BackupResult {
  success: boolean;
  message: string;
  filename?: string;
}

@Injectable()
export class BackupService {
  private backupDir: string;
  private dbHost: string;
  private dbPort: number;
  private dbName: string;
  private dbUser: string;
  private dbPassword: string;

  constructor(private configService: ConfigService) {
    this.backupDir = this.configService.get('BACKUP_DIR', '/app/backups');
    this.dbHost = this.configService.get('DATABASE_HOST', 'altshop-db');
    this.dbPort = this.configService.get('DATABASE_PORT', 5432);
    this.dbName = this.configService.get('DATABASE_NAME', 'altshop');
    this.dbUser = this.configService.get('DATABASE_USER', 'altshop');
    this.dbPassword = this.configService.get('DATABASE_PASSWORD', '');

    // Ensure backup directory exists
    if (!fs.existsSync(this.backupDir)) {
      fs.mkdirSync(this.backupDir, { recursive: true });
    }
  }

  async listBackups(): Promise<BackupInfo[]> {
    try {
      const files = fs.readdirSync(this.backupDir);
      const backups: BackupInfo[] = [];

      for (const file of files) {
        if (file.endsWith('.sql') || file.endsWith('.sql.gz')) {
          const filePath = path.join(this.backupDir, file);
          const stats = fs.statSync(filePath);
          backups.push({
            filename: file,
            size: stats.size,
            createdAt: stats.birthtime,
            path: filePath,
          });
        }
      }

      return backups.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
    } catch (error) {
      console.error('Error listing backups:', error);
      return [];
    }
  }

  async createBackup(createdBy?: number): Promise<BackupResult> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `backup_${timestamp}.sql.gz`;
    const filePath = path.join(this.backupDir, filename);

    try {
      const env = {
        ...process.env,
        PGPASSWORD: this.dbPassword,
      };

      const command = `pg_dump -h ${this.dbHost} -p ${this.dbPort} -U ${this.dbUser} -d ${this.dbName} | gzip > ${filePath}`;

      await execAsync(command, { env });

      // Verify file was created
      if (fs.existsSync(filePath)) {
        const stats = fs.statSync(filePath);
        return {
          success: true,
          message: `Backup created successfully (${this.formatSize(stats.size)})`,
          filename,
        };
      } else {
        return {
          success: false,
          message: 'Backup file was not created',
        };
      }
    } catch (error) {
      console.error('Error creating backup:', error);
      return {
        success: false,
        message: `Error creating backup: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }

  async restoreBackup(filename: string, clearExisting = false): Promise<BackupResult> {
    const filePath = path.join(this.backupDir, filename);

    if (!fs.existsSync(filePath)) {
      return {
        success: false,
        message: 'Backup file not found',
      };
    }

    try {
      const env = {
        ...process.env,
        PGPASSWORD: this.dbPassword,
      };

      if (clearExisting) {
        // Drop and recreate database (dangerous!)
        const dropCommand = `psql -h ${this.dbHost} -p ${this.dbPort} -U ${this.dbUser} -d postgres -c "DROP DATABASE IF EXISTS ${this.dbName}; CREATE DATABASE ${this.dbName};"`;
        await execAsync(dropCommand, { env });
      }

      const isGzipped = filename.endsWith('.gz');
      const restoreCommand = isGzipped
        ? `gunzip -c ${filePath} | psql -h ${this.dbHost} -p ${this.dbPort} -U ${this.dbUser} -d ${this.dbName}`
        : `psql -h ${this.dbHost} -p ${this.dbPort} -U ${this.dbUser} -d ${this.dbName} < ${filePath}`;

      await execAsync(restoreCommand, { env });

      return {
        success: true,
        message: 'Backup restored successfully',
      };
    } catch (error) {
      console.error('Error restoring backup:', error);
      return {
        success: false,
        message: `Error restoring backup: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }

  async deleteBackup(filename: string): Promise<BackupResult> {
    const filePath = path.join(this.backupDir, filename);

    if (!fs.existsSync(filePath)) {
      return {
        success: false,
        message: 'Backup file not found',
      };
    }

    try {
      fs.unlinkSync(filePath);
      return {
        success: true,
        message: 'Backup deleted successfully',
      };
    } catch (error) {
      console.error('Error deleting backup:', error);
      return {
        success: false,
        message: `Error deleting backup: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }

  async downloadBackup(filename: string): Promise<{ path: string; filename: string } | null> {
    const filePath = path.join(this.backupDir, filename);

    if (!fs.existsSync(filePath)) {
      return null;
    }

    return { path: filePath, filename };
  }

  private formatSize(bytes: number): string {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(2)} ${units[unitIndex]}`;
  }
}