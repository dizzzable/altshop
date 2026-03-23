// User types
export interface User {
  telegram_id: number
  username: string | null
  web_login?: string | null
  name: string | null
  photo_url?: string
  role: UserRole
  points: number
  language: string
  default_currency: Currency
  personal_discount: number
  purchase_discount: number
  partner_balance_currency_override?: Currency | null
  effective_partner_balance_currency?: Currency
  is_blocked: boolean
  is_bot_blocked: boolean
  created_at: string
  updated_at: string
  email?: string | null
  email_verified?: boolean
  telegram_linked?: boolean
  linked_telegram_id?: number | null
  show_link_prompt?: boolean
  requires_password_change?: boolean
  has_web_account?: boolean
  needs_web_credentials_bootstrap?: boolean
  effective_max_subscriptions?: number
  active_subscriptions_count?: number
  is_partner?: boolean
  is_partner_active?: boolean
}

export type UserRole = 'USER' | 'ADMIN' | 'DEV'

// Subscription types
export interface Subscription {
  id: number
  user_remna_id: string
  user_telegram_id: number
  status: SubscriptionStatus
  is_trial: boolean
  traffic_limit: number
  traffic_used: number
  device_limit: number
  devices_count: number
  internal_squads: string[]
  external_squad: string | null
  expire_at: string
  url: string
  device_type: DeviceType | null
  can_renew: boolean
  can_upgrade: boolean
  can_multi_renew: boolean
  renew_mode: SubscriptionRenewMode | null
  plan: PlanSnapshot
  created_at: string
  updated_at: string
}

export type SubscriptionStatus = 'ACTIVE' | 'DISABLED' | 'LIMITED' | 'EXPIRED' | 'DELETED'
export type SubscriptionRenewMode = 'STANDARD' | 'SELF_RENEW' | 'REPLACE_ON_RENEW'

export type DeviceType = 'ANDROID' | 'IPHONE' | 'WINDOWS' | 'MAC' | 'OTHER'

export interface PlanSnapshot {
  id: number
  name: string
  tag: string
  type: PlanType
  traffic_limit: number
  device_limit: number
  duration: number
  traffic_limit_strategy?: string
  internal_squads: string[]
  external_squad: string | null
}

export type PlanType = 'TRAFFIC' | 'DEVICES' | 'BOTH' | 'UNLIMITED'

// Plan types
export interface Plan {
  id: number
  name: string
  description: string | null
  tag: string | null
  type: PlanType
  availability: PlanAvailability
  traffic_limit: number
  device_limit: number
  order_index: number
  is_active: boolean
  allowed_user_ids: number[]
  internal_squads: string[]
  external_squad: string | null
  durations: PlanDuration[]
  created_at: string
  updated_at: string
}

export type PlanAvailability = 'ALL' | 'NEW' | 'EXISTING' | 'INVITED' | 'ALLOWED' | 'TRIAL'

export interface PlanDuration {
  id: number
  plan_id: number
  days: number
  prices: PlanPrice[]
}

export interface PlanPrice {
  id: number
  duration_id: number
  gateway_type: PaymentGatewayType
  price: number
  original_price: number
  currency: Currency
  discount_percent: number
  discount_source: DiscountSource
  discount: number
  supported_payment_assets?: CryptoAsset[] | null
}

export type PaymentGatewayType = 
  | 'TELEGRAM_STARS'
  | 'YOOKASSA'
  | 'YOOMONEY'
  | 'CRYPTOMUS'
  | 'HELEKET'
  | 'CRYPTOPAY'
  | 'TBANK'
  | 'ROBOKASSA'
  | 'STRIPE'
  | 'MULENPAY'
  | 'CLOUDPAYMENTS'
  | 'PAL24'
  | 'WATA'
  | 'PLATEGA'

export type Currency =
  | 'USD'
  | 'XTR'
  | 'RUB'
  | 'USDT'
  | 'TON'
  | 'BTC'
  | 'ETH'
  | 'LTC'
  | 'BNB'
  | 'DASH'
  | 'SOL'
  | 'XMR'
  | 'USDC'
  | 'TRX'
export type CryptoAsset =
  | 'USDT'
  | 'TON'
  | 'BTC'
  | 'ETH'
  | 'LTC'
  | 'BNB'
  | 'DASH'
  | 'SOL'
  | 'XMR'
  | 'USDC'
  | 'TRX'
export type DiscountSource = 'NONE' | 'PERSONAL' | 'PURCHASE'

// Payment types
export interface PaymentResult {
  id: string
  url: string | null
}

export type PurchaseType = 'NEW' | 'RENEW' | 'UPGRADE' | 'ADDITIONAL'
export type PurchaseChannel = 'WEB' | 'TELEGRAM'
export type PurchasePaymentSource = 'EXTERNAL' | 'PARTNER_BALANCE'

export interface SubscriptionPurchaseRequest {
  purchase_type?: PurchaseType
  payment_source?: PurchasePaymentSource
  channel?: PurchaseChannel
  plan_id?: number
  duration_days?: number
  device_type?: DeviceType
  gateway_type?: string
  renew_subscription_id?: number
  renew_subscription_ids?: number[]
  device_types?: DeviceType[]
  promocode?: string
  quantity?: number
  payment_asset?: CryptoAsset
}

export interface PurchaseResponse {
  transaction_id: string
  payment_url: string | null
  url?: string | null
  status: string
  message: string
}

export interface PurchaseQuoteResponse {
  price: number
  original_price: number
  currency: Currency
  settlement_price: number
  settlement_original_price: number
  settlement_currency: Currency
  discount_percent: number
  discount_source: DiscountSource
  payment_asset?: CryptoAsset | null
  quote_source: string
  quote_expires_at: string
  quote_provider_count: number
}

export interface SubscriptionPurchaseOptionsResponse {
  purchase_type: PurchaseType
  subscription_id: number
  source_plan_missing: boolean
  selection_locked: boolean
  renew_mode: SubscriptionRenewMode | null
  warning_code: string | null
  warning_message: string | null
  plans: Plan[]
}

export interface TrialEligibilityResponse {
  eligible: boolean
  reason_code: string | null
  reason_message: string | null
  requires_telegram_link: boolean
  trial_plan_id: number | null
}

export interface Transaction {
  payment_id: string
  user_telegram_id: number
  status: TransactionStatus
  purchase_type: PurchaseType
  channel?: PurchaseChannel | null
  gateway_type: PaymentGatewayType
  pricing: PriceDetails
  currency: Currency
  payment_asset?: CryptoAsset | null
  plan: PlanSnapshot
  renew_subscription_id: number | null
  renew_subscription_ids: number[] | null
  device_types: DeviceType[] | null
  is_test: boolean
  created_at: string
  updated_at: string
}

export interface TransactionHistoryResponse {
  transactions: Transaction[]
  total: number
  page: number
  limit: number
}

export type TransactionStatus = 'PENDING' | 'COMPLETED' | 'CANCELED' | 'REFUNDED' | 'FAILED'

export interface PriceDetails {
  original_amount: number
  discount_percent: number
  final_amount: number
}

// Referral types
export interface ReferralInfo {
  referral_count: number
  qualified_referral_count: number
  reward_count: number
  referral_link: string
  telegram_referral_link?: string
  web_referral_link?: string
  referral_code?: string | null
  invite_expires_at?: string | null
  remaining_slots?: number | null
  total_capacity?: number | null
  requires_regeneration?: boolean
  invite_block_reason?: string | null
  refill_step_progress?: number | null
  refill_step_target?: number | null
  points: number
}

export type ReferralInviteSource = 'BOT' | 'WEB' | 'UNKNOWN'
export type ReferralQualificationChannel = PurchaseChannel | 'UNKNOWN'
export type ReferralEventType = 'INVITED' | 'QUALIFIED'

export interface ReferralEvent {
  type: ReferralEventType
  at: string
  source?: ReferralInviteSource | null
  channel?: ReferralQualificationChannel | null
}

export interface Referral {
  telegram_id: number
  username: string | null
  name: string | null
  level: ReferralLevel
  invited_at?: string
  joined_at: string
  invite_source?: ReferralInviteSource
  is_active: boolean
  is_qualified?: boolean
  qualified_at?: string | null
  qualified_purchase_channel?: ReferralQualificationChannel | null
  rewards_issued?: number
  rewards_earned: number
  events?: ReferralEvent[]
}

export type ReferralLevel = 1 | 2 | 3

export interface ReferralListResponse {
  referrals: Referral[]
  total: number
  page: number
  limit: number
}

export type PointsExchangeType =
  | 'SUBSCRIPTION_DAYS'
  | 'GIFT_SUBSCRIPTION'
  | 'DISCOUNT'
  | 'TRAFFIC'

export interface ReferralGiftPlanOption {
  plan_id: number
  plan_name: string
}

export interface ReferralExchangeTypeOption {
  type: PointsExchangeType
  enabled: boolean
  available: boolean
  points_cost: number
  min_points: number
  max_points: number
  computed_value: number
  requires_subscription: boolean
  gift_plan_id?: number | null
  gift_duration_days?: number | null
  max_discount_percent?: number | null
  max_traffic_gb?: number | null
}

export interface ReferralExchangeOptions {
  exchange_enabled: boolean
  points_balance: number
  types: ReferralExchangeTypeOption[]
  gift_plans: ReferralGiftPlanOption[]
}

export interface ReferralExchangeExecuteRequest {
  exchange_type: PointsExchangeType
  subscription_id?: number | null
  gift_plan_id?: number | null
}

export interface ReferralExchangeExecuteResultPayload {
  days_added?: number | null
  traffic_gb_added?: number | null
  discount_percent_added?: number | null
  gift_promocode?: string | null
  gift_plan_name?: string | null
  gift_duration_days?: number | null
}

export interface ReferralExchangeExecuteResponse {
  success: boolean
  exchange_type: PointsExchangeType
  points_spent: number
  points_balance_after: number
  result: ReferralExchangeExecuteResultPayload
}

// Partner types
export interface PartnerLevelSetting {
  level: 1 | 2 | 3
  referrals_count: number
  earned_amount: number
  global_percent: number
  individual_percent?: number | null
  individual_fixed_amount?: number | null
  effective_percent?: number | null
  effective_fixed_amount?: number | null
  uses_global_value: boolean
}

export interface PartnerInfo {
  is_partner: boolean
  is_active?: boolean
  can_withdraw?: boolean
  apply_support_url?: string | null
  effective_currency?: Currency
  min_withdrawal_rub?: number
  min_withdrawal_display?: number
  balance: number
  balance_display?: number
  total_earned: number
  total_earned_display?: number
  total_withdrawn: number
  total_withdrawn_display?: number
  referrals_count: number
  level2_referrals_count: number
  level3_referrals_count: number
  referral_link?: string | null
  telegram_referral_link?: string | null
  web_referral_link?: string | null
  use_global_settings?: boolean
  effective_reward_type?: 'PERCENT' | 'FIXED_AMOUNT'
  effective_accrual_strategy?: 'ON_FIRST_PAYMENT' | 'ON_EACH_PAYMENT'
  level_settings?: PartnerLevelSetting[]
}

export interface PartnerEarning {
  id: number
  referral_telegram_id: number
  referral_username: string | null
  level: PartnerLevel
  payment_amount: number
  payment_amount_display?: number
  percent: number
  earned_amount: number
  earned_amount_display?: number
  display_currency?: Currency
  created_at: string
}

export type PartnerLevel = 1 | 2 | 3

export interface PartnerEarningsListResponse {
  earnings: PartnerEarning[]
  total: number
  page: number
  limit: number
}

export interface PartnerReferral {
  telegram_id: number
  username: string | null
  name: string | null
  level: number
  joined_at: string
  invite_source: ReferralInviteSource
  is_active: boolean
  is_paid: boolean
  first_paid_at: string | null
  total_paid_amount: number
  total_earned: number
  total_paid_amount_display?: number
  total_earned_display?: number
  display_currency?: Currency
}

export interface PartnerReferralsListResponse {
  referrals: PartnerReferral[]
  total: number
  page: number
  limit: number
}

export interface PartnerWithdrawal {
  id: number
  amount: number
  display_amount?: number
  display_currency?: Currency
  requested_amount?: number | null
  requested_currency?: Currency | null
  quote_rate?: number | null
  quote_source?: string | null
  status: WithdrawalStatus
  method: string
  requisites: string
  admin_comment: string | null
  created_at: string
  updated_at: string
}

export type WithdrawalStatus = 'PENDING' | 'APPROVED' | 'COMPLETED' | 'REJECTED' | 'CANCELED'

export interface PartnerWithdrawalsListResponse {
  withdrawals: PartnerWithdrawal[]
}

// Promocode types
export interface PromocodeActivateResult {
  message: string
  reward?: {
    type: PromocodeRewardType
    value: number
  }
  next_step?: 'SELECT_SUBSCRIPTION' | 'CREATE_NEW' | null
  available_subscriptions?: number[]
  allowed_plan_ids?: number[]
}

export interface PromocodeActivationHistoryItem {
  id: number
  code: string
  reward: {
    type: PromocodeRewardType
    value: number
  }
  target_subscription_id: number | null
  activated_at: string
}

export interface PromocodeActivationHistoryResponse {
  activations: PromocodeActivationHistoryItem[]
  total: number
  page: number
  limit: number
}

export type PromocodeRewardType = 
  | 'DURATION'
  | 'TRAFFIC'
  | 'DEVICES'
  | 'SUBSCRIPTION'
  | 'PERSONAL_DISCOUNT'
  | 'PURCHASE_DISCOUNT'

// Auth types
export interface TelegramAuthData {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

export interface AuthSessionResponse {
  expires_in: number
  is_new_user?: boolean
  auth_source?: string | null
}

export interface PasswordChangeResponse {
  message: string
}

export interface TelegramLinkRequestResponse {
  message: string
  delivered: boolean
  expires_in_seconds: number
}

export interface TelegramLinkConfirmResponse {
  message: string
  linked_telegram_id: number
}

export interface TelegramLinkStatusResponse {
  telegram_linked: boolean
  linked_telegram_id: number | null
  show_link_prompt: boolean
}

export interface WebBrandingResponse {
  project_name: string
  web_title: string
  default_locale: WebLocale
  supported_locales: WebLocale[]
  support_url?: string | null
}

export interface RegistrationAccessRequirements {
  access_mode: string
  rules_required: boolean
  channel_required: boolean
  rules_link?: string | null
  channel_link?: string | null
  requires_telegram_id: boolean
  tg_id_helper_bot_link: string
  verification_bot_link?: string | null
}

export type AccessUnmetRequirementCode =
  | 'RULES_ACCEPTANCE_REQUIRED'
  | 'TELEGRAM_LINK_REQUIRED'
  | 'CHANNEL_SUBSCRIPTION_REQUIRED'
  | 'CHANNEL_VERIFICATION_UNAVAILABLE'

export interface AccessStatus {
  access_mode: string
  rules_required: boolean
  channel_required: boolean
  requires_telegram_id: boolean
  access_level: 'full' | 'read_only' | 'blocked'
  channel_check_status: 'not_required' | 'verified' | 'required_unverified' | 'unavailable'
  rules_accepted: boolean
  telegram_linked: boolean
  channel_verified: boolean
  linked_telegram_id?: number | null
  rules_link?: string | null
  channel_link?: string | null
  tg_id_helper_bot_link: string
  verification_bot_link?: string | null
  unmet_requirements: AccessUnmetRequirementCode[]
  can_use_product_features: boolean
  can_view_product_screens: boolean
  can_mutate_product: boolean
  can_purchase: boolean
  should_redirect_to_access_screen: boolean
  invite_locked: boolean
}

export interface WebAccessBlockedErrorDetail {
  code: string
  message?: string
  unmet_requirements?: AccessUnmetRequirementCode[]
}

export interface GenericMessageResponse {
  message: string
}

export type WebLocale = 'ru' | 'en'

// API types
export interface ApiResponse<T> {
  data: T
  error?: ApiError
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: Pagination
}

export interface Pagination {
  total: number
  page: number
  limit: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

// Device types
export interface Device {
  hwid: string
  device_type: string
  first_connected: string | null
  last_connected: string | null
  country: string | null
  ip: string | null
}

export interface DeviceListResponse {
  devices: Device[]
  subscription_id: number
  device_limit: number
  devices_count: number
}

export interface SubscriptionListResponse {
  subscriptions: Subscription[]
}

// Notification types
export type UserNotificationType =
  | 'EXPIRES_IN_3_DAYS'
  | 'EXPIRES_IN_2_DAYS'
  | 'EXPIRES_IN_1_DAYS'
  | 'EXPIRED'
  | 'LIMITED'
  | 'EXPIRED_1_DAY_AGO'
  | 'REFERRAL_ATTACHED'
  | 'REFERRAL_REWARD'
  | 'REFERRAL_QUALIFIED'
  | 'PARTNER_REFERRAL_REGISTERED'
  | 'PARTNER_EARNING'
  | 'PARTNER_WITHDRAWAL_REQUEST_CREATED'
  | 'PARTNER_WITHDRAWAL_UNDER_REVIEW'
  | 'PARTNER_WITHDRAWAL_COMPLETED'
  | 'PARTNER_WITHDRAWAL_REJECTED'

export interface UserNotificationItem {
  id: number
  type: UserNotificationType | string
  title: string
  message: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface UserNotificationListResponse {
  notifications: UserNotificationItem[]
  total: number
  page: number
  limit: number
  unread: number
}

export interface UnreadCountResponse {
  unread: number
}

export interface MarkReadResponse {
  updated: number
}

// Common types
export interface BaseEntity {
  id: number
  created_at: string
  updated_at: string
}

export type SortOrder = 'asc' | 'desc'

export interface SortOptions {
  field: string
  order: SortOrder
}
