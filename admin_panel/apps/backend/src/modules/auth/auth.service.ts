import { Injectable, UnauthorizedException, OnModuleInit, Logger } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcrypt';
import { AdminUser, AdminRole } from './entities/admin-user.entity';

export interface JwtPayload {
  sub: string;
  username: string;
  role: AdminRole;
}

@Injectable()
export class AuthService implements OnModuleInit {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    @InjectRepository(AdminUser)
    private adminUserRepository: Repository<AdminUser>,
    private jwtService: JwtService,
    private configService: ConfigService,
    private dataSource: DataSource,
  ) {}

  async onModuleInit() {
    // Create admin_users table if not exists
    const tableCreated = await this.ensureAdminUsersTable();
    
    if (!tableCreated) {
      this.logger.error('Failed to ensure admin_users table exists');
      return;
    }
    
    // Create default admin user if not exists
    const adminUsername = this.configService.get('ADMIN_USERNAME', 'admin');
    
    try {
      const existingAdmin = await this.adminUserRepository.findOne({
        where: { username: adminUsername },
      });

      if (!existingAdmin) {
        const adminPassword = this.configService.get('ADMIN_PASSWORD', 'admin123');
        const adminTelegramId = this.configService.get('ADMIN_TELEGRAM_ID');
        
        const hashedPassword = await bcrypt.hash(adminPassword, 10);
        
        const admin = this.adminUserRepository.create({
          username: adminUsername,
          password: hashedPassword,
          telegramId: adminTelegramId,
          role: AdminRole.SUPER_ADMIN,
          isActive: true,
        });
        
        await this.adminUserRepository.save(admin);
        this.logger.log('✅ Default admin user created');
      }
    } catch (error) {
      this.logger.error('Failed to create default admin user:', error);
    }
  }

  private async ensureAdminUsersTable(): Promise<boolean> {
    try {
      // Always try to create the table (IF NOT EXISTS handles duplicates)
      this.logger.log('Ensuring admin_users table exists...');
      
      await this.dataSource.query(`
        CREATE TABLE IF NOT EXISTS admin_users (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          username VARCHAR(50) UNIQUE NOT NULL,
          password VARCHAR(255) NOT NULL,
          telegram_id BIGINT UNIQUE,
          role VARCHAR(20) DEFAULT 'admin',
          is_active BOOLEAN DEFAULT true,
          last_login TIMESTAMP,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      
      this.logger.log('✅ admin_users table ready');
      return true;
    } catch (error) {
      this.logger.error('Failed to ensure admin_users table:', error);
      return false;
    }
  }

  async validateUser(username: string, password: string): Promise<AdminUser | null> {
    const user = await this.adminUserRepository.findOne({
      where: { username, isActive: true },
    });

    if (user && (await bcrypt.compare(password, user.password))) {
      return user;
    }
    return null;
  }

  async login(user: AdminUser) {
    const payload: JwtPayload = {
      sub: user.id,
      username: user.username,
      role: user.role,
    };

    // Update last login
    await this.adminUserRepository.update(user.id, {
      lastLogin: new Date(),
    });

    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        username: user.username,
        role: user.role,
        telegramId: user.telegramId,
      },
    };
  }

  async validateToken(token: string): Promise<JwtPayload> {
    try {
      return this.jwtService.verify(token);
    } catch {
      throw new UnauthorizedException('Invalid token');
    }
  }

  async getProfile(userId: string): Promise<Omit<AdminUser, 'password'>> {
    const user = await this.adminUserRepository.findOne({
      where: { id: userId },
    });

    if (!user) {
      throw new UnauthorizedException('User not found');
    }

    const { password, ...result } = user;
    return result;
  }

  async changePassword(userId: string, oldPassword: string, newPassword: string): Promise<void> {
    const user = await this.adminUserRepository.findOne({
      where: { id: userId },
    });

    if (!user) {
      throw new UnauthorizedException('User not found');
    }

    const isValid = await bcrypt.compare(oldPassword, user.password);
    if (!isValid) {
      throw new UnauthorizedException('Invalid old password');
    }

    const hashedPassword = await bcrypt.hash(newPassword, 10);
    await this.adminUserRepository.update(userId, { password: hashedPassword });
  }
}