import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
  ManyToOne,
  JoinColumn,
} from 'typeorm';

export enum UserRole {
  USER = 'user',
  ADMIN = 'admin',
  MODERATOR = 'moderator',
}

export enum Locale {
  RU = 'ru',
  EN = 'en',
}

@Entity('users')
export class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'telegram_id', type: 'bigint', unique: true })
  telegramId: string;

  @Column({ nullable: true })
  username: string;

  @Column({ name: 'referral_code', unique: true })
  referralCode: string;

  @Column()
  name: string;

  @Column({
    type: 'enum',
    enum: UserRole,
    default: UserRole.USER,
  })
  role: UserRole;

  @Column({
    type: 'enum',
    enum: Locale,
    default: Locale.RU,
  })
  language: Locale;

  @Column({ name: 'personal_discount', default: 0 })
  personalDiscount: number;

  @Column({ name: 'purchase_discount', default: 0 })
  purchaseDiscount: number;

  @Column({ default: 0 })
  points: number;

  @Column({ name: 'is_blocked', default: false })
  isBlocked: boolean;

  @Column({ name: 'is_bot_blocked', default: false })
  isBotBlocked: boolean;

  @Column({ name: 'is_rules_accepted', default: true })
  isRulesAccepted: boolean;

  @Column({ name: 'max_subscriptions', nullable: true })
  maxSubscriptions: number;

  @Column({ name: 'current_subscription_id', nullable: true })
  currentSubscriptionId: number;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}