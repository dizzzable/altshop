import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from 'typeorm';

export enum AuditAction {
  CREATE = 'create',
  UPDATE = 'update',
  DELETE = 'delete',
  LOGIN = 'login',
  LOGOUT = 'logout',
  BROADCAST = 'broadcast',
  SETTINGS_CHANGE = 'settings_change',
  USER_BAN = 'user_ban',
  USER_UNBAN = 'user_unban',
  SUBSCRIPTION_GRANT = 'subscription_grant',
  SUBSCRIPTION_REVOKE = 'subscription_revoke',
  PAYMENT = 'payment',
  PROMOCODE_USE = 'promocode_use',
}

export enum AuditEntity {
  USER = 'user',
  SUBSCRIPTION = 'subscription',
  PLAN = 'plan',
  PROMOCODE = 'promocode',
  SETTINGS = 'settings',
  BROADCAST = 'broadcast',
  ADMIN = 'admin',
  BUTTON = 'button',
  BANNER = 'banner',
  GATEWAY = 'gateway',
}

@Entity('audit_logs')
export class AuditLog {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({
    type: 'enum',
    enum: AuditAction,
  })
  action: AuditAction;

  @Column({
    name: 'entity_type',
    type: 'enum',
    enum: AuditEntity,
  })
  entityType: AuditEntity;

  @Column({ name: 'entity_id', nullable: true })
  entityId: string;

  @Column({ name: 'admin_id', type: 'bigint', nullable: true })
  adminId: string;

  @Column({ name: 'admin_username', length: 100, nullable: true })
  adminUsername: string;

  @Column({ name: 'old_value', type: 'jsonb', nullable: true })
  oldValue: Record<string, any>;

  @Column({ name: 'new_value', type: 'jsonb', nullable: true })
  newValue: Record<string, any>;

  @Column({ type: 'text', nullable: true })
  description: string;

  @Column({ name: 'ip_address', length: 50, nullable: true })
  ipAddress: string;

  @Column({ name: 'user_agent', type: 'text', nullable: true })
  userAgent: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}