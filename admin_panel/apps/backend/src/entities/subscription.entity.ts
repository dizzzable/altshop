import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export enum SubscriptionStatus {
  ACTIVE = 'active',
  EXPIRED = 'expired',
  DISABLED = 'disabled',
  LIMITED = 'limited',
}

@Entity('subscriptions')
export class Subscription {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'user_telegram_id', type: 'bigint' })
  userTelegramId: string;

  @Column({ name: 'plan_id' })
  planId: number;

  @Column({ name: 'remnawave_uuid', type: 'uuid', nullable: true })
  remnawaveUuid: string;

  @Column({ name: 'short_uuid', nullable: true })
  shortUuid: string;

  @Column({
    type: 'enum',
    enum: SubscriptionStatus,
    default: SubscriptionStatus.ACTIVE,
  })
  status: SubscriptionStatus;

  @Column({ name: 'expires_at', type: 'timestamp' })
  expiresAt: Date;

  @Column({ name: 'traffic_used', type: 'bigint', default: 0 })
  trafficUsed: string;

  @Column({ name: 'traffic_limit', type: 'bigint', default: 0 })
  trafficLimit: string;

  @Column({ name: 'is_auto_renew', default: false })
  isAutoRenew: boolean;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}