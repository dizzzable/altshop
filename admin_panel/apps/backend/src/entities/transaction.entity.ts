import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
} from 'typeorm';

export enum TransactionStatus {
  PENDING = 'pending',
  COMPLETED = 'completed',
  FAILED = 'failed',
  REFUNDED = 'refunded',
}

export enum TransactionType {
  PURCHASE = 'purchase',
  RENEWAL = 'renewal',
  UPGRADE = 'upgrade',
  REFUND = 'refund',
}

@Entity('transactions')
export class Transaction {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'user_telegram_id', type: 'bigint' })
  userTelegramId: string;

  @Column({ name: 'subscription_id', nullable: true })
  subscriptionId: number;

  @Column({ name: 'plan_id' })
  planId: number;

  @Column({ type: 'decimal', precision: 10, scale: 2 })
  amount: number;

  @Column()
  currency: string;

  @Column({
    type: 'enum',
    enum: TransactionStatus,
    default: TransactionStatus.PENDING,
  })
  status: TransactionStatus;

  @Column({
    type: 'enum',
    enum: TransactionType,
    default: TransactionType.PURCHASE,
  })
  type: TransactionType;

  @Column({ name: 'payment_gateway', nullable: true })
  paymentGateway: string;

  @Column({ name: 'external_id', nullable: true })
  externalId: string;

  @Column({ type: 'jsonb', nullable: true })
  metadata: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}