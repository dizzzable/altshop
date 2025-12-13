import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export enum PromocodeType {
  DISCOUNT = 'discount',
  BONUS = 'bonus',
  TRIAL = 'trial',
}

@Entity('promocodes')
export class Promocode {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ unique: true })
  code: string;

  @Column({
    type: 'enum',
    enum: PromocodeType,
    default: PromocodeType.DISCOUNT,
  })
  type: PromocodeType;

  @Column({ default: 0 })
  discount: number;

  @Column({ name: 'bonus_days', default: 0 })
  bonusDays: number;

  @Column({ name: 'max_activations', default: 1 })
  maxActivations: number;

  @Column({ name: 'current_activations', default: 0 })
  currentActivations: number;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ name: 'valid_from', type: 'timestamp', nullable: true })
  validFrom: Date;

  @Column({ name: 'valid_until', type: 'timestamp', nullable: true })
  validUntil: Date;

  @Column({ name: 'plan_ids', type: 'int', array: true, nullable: true })
  planIds: number[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}

@Entity('promocode_activations')
export class PromocodeActivation {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'promocode_id' })
  promocodeId: number;

  @Column({ name: 'user_telegram_id', type: 'bigint' })
  userTelegramId: string;

  @CreateDateColumn({ name: 'activated_at' })
  activatedAt: Date;
}