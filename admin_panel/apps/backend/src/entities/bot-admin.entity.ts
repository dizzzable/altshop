import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from 'typeorm';

export enum AdminRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  MODERATOR = 'moderator',
}

@Entity('bot_admins')
export class BotAdmin {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'telegram_id', type: 'bigint', unique: true })
  telegramId: string;

  @Column({ length: 100, nullable: true })
  username: string;

  @Column({ name: 'first_name', length: 100, nullable: true })
  firstName: string;

  @Column({ name: 'last_name', length: 100, nullable: true })
  lastName: string;

  @Column({
    type: 'enum',
    enum: AdminRole,
    default: AdminRole.ADMIN,
  })
  role: AdminRole;

  @Column({ type: 'jsonb', default: [] })
  permissions: string[];

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ name: 'added_by', type: 'bigint', nullable: true })
  addedBy: string;

  @Column({ name: 'last_activity', type: 'timestamp', nullable: true })
  lastActivity: Date;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}