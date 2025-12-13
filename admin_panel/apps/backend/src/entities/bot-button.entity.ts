import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from 'typeorm';

export enum ButtonType {
  MAIN_MENU = 'main_menu',
  INLINE = 'inline',
  REPLY = 'reply',
}

export enum ButtonAction {
  URL = 'url',
  CALLBACK = 'callback',
  STATE = 'state',
  WEBAPP = 'webapp',
}

@Entity('bot_buttons')
export class BotButton {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ length: 100 })
  name: string;

  @Column({ length: 255 })
  text: string;

  @Column({ name: 'text_key', length: 100, nullable: true })
  textKey: string;

  @Column({
    type: 'enum',
    enum: ButtonType,
    default: ButtonType.INLINE,
  })
  type: ButtonType;

  @Column({
    type: 'enum',
    enum: ButtonAction,
    default: ButtonAction.CALLBACK,
  })
  action: ButtonAction;

  @Column({ name: 'action_data', length: 500, nullable: true })
  actionData: string;

  @Column({ name: 'parent_menu', length: 100, nullable: true })
  parentMenu: string;

  @Column({ default: 0 })
  position: number;

  @Column({ default: 0 })
  row: number;

  @Column({ length: 50, nullable: true })
  emoji: string;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ name: 'requires_admin', default: false })
  requiresAdmin: boolean;

  @Column({ name: 'requires_subscription', default: false })
  requiresSubscription: boolean;

  @Column({ type: 'jsonb', default: {} })
  conditions: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}