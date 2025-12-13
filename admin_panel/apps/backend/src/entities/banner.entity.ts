import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from 'typeorm';

export enum BannerType {
  WELCOME = 'welcome',
  MENU = 'menu',
  SUBSCRIPTION = 'subscription',
  DASHBOARD = 'dashboard',
  PROMO = 'promo',
  CUSTOM = 'custom',
}

@Entity('banners')
export class Banner {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ length: 100 })
  name: string;

  @Column({
    type: 'enum',
    enum: BannerType,
    default: BannerType.CUSTOM,
  })
  type: BannerType;

  @Column({ name: 'file_path', length: 500, nullable: true })
  filePath: string;

  @Column({ name: 'file_id', length: 255, nullable: true })
  fileId: string;

  @Column({ length: 10, default: 'ru' })
  locale: string;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ default: 0 })
  priority: number;

  @Column({ name: 'start_date', type: 'timestamp', nullable: true })
  startDate: Date;

  @Column({ name: 'end_date', type: 'timestamp', nullable: true })
  endDate: Date;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}