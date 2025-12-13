import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';

export enum PlanType {
  STANDARD = 'standard',
  PREMIUM = 'premium',
  TRIAL = 'trial',
}

export enum PlanAvailability {
  PUBLIC = 'public',
  PRIVATE = 'private',
  HIDDEN = 'hidden',
}

export enum TrafficLimitStrategy {
  NO_RESET = 'no_reset',
  DAY = 'day',
  WEEK = 'week',
  MONTH = 'month',
}

@Entity('plans')
export class Plan {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'order_index' })
  orderIndex: number;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({
    type: 'enum',
    enum: PlanType,
    default: PlanType.STANDARD,
  })
  type: PlanType;

  @Column({
    type: 'enum',
    enum: PlanAvailability,
    default: PlanAvailability.PUBLIC,
  })
  availability: PlanAvailability;

  @Column({ unique: true })
  name: string;

  @Column({ nullable: true })
  description: string;

  @Column({ nullable: true })
  tag: string;

  @Column({ name: 'traffic_limit', default: 0 })
  trafficLimit: number;

  @Column({ name: 'device_limit', default: 1 })
  deviceLimit: number;

  @Column({ name: 'subscription_count', default: 1 })
  subscriptionCount: number;

  @Column({
    name: 'traffic_limit_strategy',
    type: 'enum',
    enum: TrafficLimitStrategy,
    default: TrafficLimitStrategy.NO_RESET,
  })
  trafficLimitStrategy: TrafficLimitStrategy;

  @Column({ name: 'allowed_user_ids', type: 'bigint', array: true, nullable: true })
  allowedUserIds: string[];

  @Column({ name: 'internal_squads', type: 'uuid', array: true })
  internalSquads: string[];

  @Column({ name: 'external_squad', type: 'uuid', array: true, nullable: true })
  externalSquad: string[];

  @OneToMany(() => PlanDuration, (duration) => duration.plan)
  durations: PlanDuration[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}

@Entity('plan_durations')
export class PlanDuration {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'plan_id' })
  planId: number;

  @Column()
  days: number;

  plan: Plan;

  @OneToMany(() => PlanPrice, (price) => price.planDuration)
  prices: PlanPrice[];
}

export enum Currency {
  RUB = 'RUB',
  USD = 'USD',
  EUR = 'EUR',
  XTR = 'XTR',
}

@Entity('plan_prices')
export class PlanPrice {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'plan_duration_id' })
  planDurationId: number;

  @Column({
    type: 'enum',
    enum: Currency,
    default: Currency.RUB,
  })
  currency: Currency;

  @Column({ type: 'decimal', precision: 10, scale: 2 })
  price: number;

  planDuration: PlanDuration;
}