import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn, OneToMany } from 'typeorm';

export enum BroadcastStatus {
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  CANCELED = 'CANCELED',
  DELETED = 'DELETED',
  ERROR = 'ERROR',
}

export enum BroadcastAudience {
  ALL = 'ALL',
  PLAN = 'PLAN',
  SUBSCRIBED = 'SUBSCRIBED',
  UNSUBSCRIBED = 'UNSUBSCRIBED',
  EXPIRED = 'EXPIRED',
  TRIAL = 'TRIAL',
}

export enum BroadcastMessageStatus {
  SENT = 'SENT',
  FAILED = 'FAILED',
  EDITED = 'EDITED',
  DELETED = 'DELETED',
  PENDING = 'PENDING',
}

@Entity('broadcasts')
export class Broadcast {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'uuid', unique: true })
  task_id: string;

  @Column({
    type: 'enum',
    enum: BroadcastStatus,
    enumName: 'broadcast_status',
  })
  status: BroadcastStatus;

  @Column({
    type: 'enum',
    enum: BroadcastAudience,
    enumName: 'broadcast_audience',
  })
  audience: BroadcastAudience;

  @Column({ type: 'int' })
  total_count: number;

  @Column({ type: 'int' })
  success_count: number;

  @Column({ type: 'int' })
  failed_count: number;

  @Column({ type: 'jsonb' })
  payload: Record<string, any>;

  @CreateDateColumn()
  created_at: Date;

  @UpdateDateColumn()
  updated_at: Date;

  @OneToMany(() => BroadcastMessage, (message) => message.broadcast)
  messages: BroadcastMessage[];
}

@Entity('broadcast_messages')
export class BroadcastMessage {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  broadcast_id: number;

  @Column({ type: 'bigint' })
  user_id: number;

  @Column({ type: 'bigint', nullable: true })
  message_id: number;

  @Column({
    type: 'enum',
    enum: BroadcastMessageStatus,
    enumName: 'broadcast_message_status',
  })
  status: BroadcastMessageStatus;

  broadcast: Broadcast;
}