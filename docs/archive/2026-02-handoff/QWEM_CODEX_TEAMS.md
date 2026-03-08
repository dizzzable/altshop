# **AltShop v0.9.3 - Comprehensive Technical Codex**

## **Collaborative Analysis Document**
### **Status: PARITY CLOSURE PASS IMPLEMENTED (v5.5)**
### **Created by: Qwen Code**
### **Date: 2026-02-20**

---

## **Table of Contents**

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Services Layer](#3-services-layer)
4. [Database Layer](#4-database-layer)
5. [Bot Layer](#5-bot-layer)
6. [API Layer](#6-api-layer)
7. [Payment Gateways](#7-payment-gateways)
8. [Background Tasks](#8-background-tasks)
9. [Frontend Web App](#9-frontend-web-app)
10. [Infrastructure](#10-infrastructure)
11. [Configuration](#11-configuration)
12. [Security](#12-security)
13. [Internationalization](#13-internationalization)
14. [Deployment](#14-deployment)
15. [Known Issues & Technical Debt](#15-known-issues--technical-debt)
16. [Areas Requiring Further Study](#16-areas-requiring-further-study)
17. [Codex Collaborative Addendum (v5.4)](#17-codex-collaborative-addendum-v54)
18. [Consensus vs Disagreement Matrix](#18-consensus-vs-disagreement-matrix)
19. [Joint Prioritized Remediation Backlog](#19-joint-prioritized-remediation-backlog)
20. [Coverage Delta vs Section 16](#20-coverage-delta-vs-section-16)
21. [Document Status Update](#21-document-status-update)
22. [Codex Parity Verification & Closure (v5.5)](#22-codex-parity-verification--closure-v55)

---

## **1. Project Overview**

### **1.1 Project Information**

| Attribute | Value |
|-----------|-------|
| **Name** | AltShop (Remnashop Fork) |
| **Version** | 0.9.3 |
| **License** | MIT License |
| **Author** | snoups |
| **Repository** | https://github.com/snoups/remnashop |
| **Python Version** | 3.12+ |
| **Lines of Code** | ~60,000 |
| **Total Files** | 380+ |
| **Python Files** | 288 |
| **TypeScript Files** | 42 |
| **Documentation Files** | 35 |

### **1.2 Purpose**

**AltShop** is a production-ready **Telegram bot for selling VPN subscriptions**. It integrates with the **Remnawave VPN management panel** to provide:

- Subscription purchase and management
- Payment processing (10 gateways, 7 implemented)
- 3-level referral rewards program
- 3-level partner commission system
- Administrative dashboard via Telegram
- Web application for user self-service
- Mass broadcast messaging
- Database backup/restore
- User import from 3X-UI panels
- Multi-language support (Russian, English)
- Multi-subscription support (up to 5 per user)

### **1.3 Technology Stack**

**Backend:**
- FastAPI 0.120.2+ (REST API, webhooks)
- aiogram 3.22.0 (Telegram Bot Framework)
- aiogram-dialog 2.4.0 (FSM dialog management)
- SQLAlchemy 2.0 (ORM)
- Alembic 1.16.5 (Database migrations)
- AsyncPG 0.30.0 (PostgreSQL driver)
- dishka 1.6.0 (Dependency Injection)
- Taskiq 0.11.19 (Background tasks)
- Taskiq-Redis 1.1.2 (Redis broker)
- Pydantic 2.4.1-2.12 (Data validation)
- fluentogram 1.2.1 (FTL i18n)
- msgspec 0.19.0 (JSON serialization)
- loguru 0.7.3 (Logging)
- redis 6.4.0 (Redis client)
- remnawave 2.3.2+ (VPN panel SDK)
- cryptography 46.0.3+ (Fernet encryption)
- bcrypt 4.0.0+ (Password hashing)
- python-jose 3.4.0+ (JWT)
- uvicorn 0.38.0+ (ASGI server)

**Frontend:**
- React 19.2.4
- TypeScript 5.7.0
- Vite 6.0.0
- TailwindCSS 4.0.0
- Radix UI (17 components)
- Zustand 5.0.0 (State management)
- TanStack Query 5.60 (Data fetching)
- React Router 7.0.0
- Axios 1.7.0

**Infrastructure:**
- PostgreSQL 17
- Redis/Valkey 9
- Nginx 1.28
- Docker Compose
- Node.js 20 (web app build)

---

## **2. Architecture**

### **2.1 Layered Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Telegram │  │ Remnawave│  │ Payment  │  │  Admin   │    │
│  │   API    │  │  Panel   │  │ Gateways │  │  Panel   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │ Webhook     │ API/SDK     │ Webhook     │ HTTP
        │             │             │             │
┌───────▼─────────────▼─────────────▼─────────────▼───────────┐
│                  NGINX (Reverse Proxy)                       │
│  SSL Termination | HTTP/2 | Gzip | WebSocket | Docker DNS   │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│  AltShop Bot  │  │ Admin Backend │  │ Admin Frontend│
│  FastAPI +    │  │   Node.js     │  │  React/Vue    │
│   aiogram     │  │   Port 4000   │  │   Port 4080   │
│   Port 5000   │  │               │  │               │
└───────┬───────┘  └───────────────┘  └───────────────┘
        │
  ┌─────┴─────┐
  │           │
┌─▼────┐  ┌──▼──────────────────────────────────────────┐
│ Redis│  │           AltShop Application               │
│ Cache│  │  ┌─────────────────────────────────────┐    │
│ Queue│  │  │         Middleware Chain            │    │
│ Lock │  │  │ Error→Access→Rules→User→Channel    │    │
└──────┘  │  └─────────────────────────────────────┘    │
          │                    │                        │
          │  ┌─────────────────▼─────────────────┐      │
          │  │         Router/Handler Layer       │      │
          │  │  Menu | Subscription | Dashboard   │      │
          │  └───────────────────────────────────┘      │
          │                    │                        │
          │  ┌─────────────────▼─────────────────┐      │
          │  │          Service Layer            │      │
          │  │ 15 Services (User, Payment, etc.) │      │
          │  └───────────────────────────────────┘      │
          │                    │                        │
          │  ┌─────────────────▼─────────────────┐      │
          │  │       Infrastructure Layer        │      │
          │  │ Repositories | Taskiq | Gateways │      │
          │  └───────────────────────────────────┘      │
          └────────────────────┬────────────────────────┘
                               │
                  ┌────────────▼────────────┐
                  │    PostgreSQL 17        │
                  │  18 Tables | 28 Migrations │
                  └─────────────────────────┘
```

### **2.2 Design Patterns**

**1. Dependency Injection (dishka)**
```python
# Container setup in src/infrastructure/di/ioc.py
def create_container(config: AppConfig, bg_manager_factory: BgManagerFactory) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
    }
    container = make_async_container(*get_providers(), FastapiProvider(), context=context)
    return container

# Provider example
class ServicesProvider(Provider):
    scope = Scope.APP
    auth_service = provide(source=AuthService, scope=Scope.REQUEST)
    user_service = provide(source=UserService, scope=Scope.REQUEST)
```

**Scope Hierarchy:**
- `Scope.REQUEST` - Per request/update (most services)
- `Scope.APP` - Application lifetime (config, bot, engine)

**2. Repository Pattern**
```python
class BaseRepository:
    session: AsyncSession
    
    async def _get_one(model, *conditions) -> Optional[T]
    async def _get_many(model, *conditions) -> list[T]
    async def create(instance) -> T
    async def update(model_id, **data) -> Optional[T]
    async def delete(model_id) -> bool

class UserRepository(BaseRepository):
    async def get_by_partial_name(self, query: str) -> list[User]
    async def get_by_referral_code(self, code: str) -> Optional[User]
    async def filter_by_role(self, role: UserRole) -> list[User]
```

**3. Unit of Work Pattern**
```python
class UnitOfWork:
    session_pool: async_sessionmaker[AsyncSession]
    session: Optional[AsyncSession]
    repository: RepositoriesFacade

    async def __aenter__(self) -> Self:
        self.session = await self.session_pool().__aenter__()
        self.repository = RepositoriesFacade(session=self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.commit()  # Auto-commit on success
        else:
            await self.rollback()  # Auto-rollback on exception
        await self.session.close()
```

**4. DTO (Data Transfer Object) Pattern**
```python
class UserDto(BaseDto):
    telegram_id: int
    username: Optional[str]
    role: UserRole
    personal_discount: int
    points: int
    
    @property
    def is_privileged(self) -> bool: ...
    @property
    def has_subscription(self) -> bool: ...
```

**5. Service Layer Pattern**
```python
class BaseService(ABC):
    config: AppConfig
    bot: Bot
    redis_client: Redis
    translator_hub: TranslatorHub

class UserService(BaseService):
    uow: UnitOfWork
    
    async def create(self, aiogram_user) -> UserDto
    async def get(self, telegram_id) -> Optional[UserDto]
    async def update(self, user: UserDto) -> Optional[UserDto]
```

**6. Middleware Chain**
```
Update Received
    ↓
ErrorMiddleware (OUTER) - Catches all exceptions
    ↓
AccessMiddleware (OUTER) - Checks access mode
    ↓
RulesMiddleware (OUTER) - Enforces rules acceptance
    ↓
UserMiddleware (OUTER) - Loads/creates user
    ↓
ChannelMiddleware (OUTER) - Channel subscription check
    ↓
ThrottlingMiddleware (OUTER) - Rate limiting
    ↓
[Handler Execution]
    ↓
GarbageMiddleware (INNER) - Auto-delete messages
```

**7. FSM (Finite State Machine) Dialogs**
```python
class MainMenu(StatesGroup):
    MAIN = State()
    DEVICES = State()
    CONNECT_DEVICE = State()
    INVITE = State()
    EXCHANGE = State()
    # ... 16 states total

menu = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-main-menu"),
    Row(
        SwitchTo(text=I18nFormat("btn-menu-connect"), ...),
    ),
    state=MainMenu.MAIN,
    getter=menu_getter,
)

router = Dialog(menu, devices, connect_device, invite, exchange, ...)
```

**8. Event-Driven Architecture (Taskiq)**
```python
@broker.task
@inject
async def purchase_subscription_task(
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    # Background processing
    ...

# Task triggering
await purchase_subscription_task.kiq(transaction, subscription)

# Scheduled tasks
@broker.task(schedule=[{"cron": "0 3 * * *"}])
async def cleanup_expired_subscriptions_task(...):
    ...
```

**9. Factory Pattern (Payment Gateways)**
```python
class PaymentGatewayFactory(Protocol):
    def __call__(self, gateway: PaymentGatewayDto) -> BasePaymentGateway: ...

# Usage
class PaymentGatewayService(BaseService):
    payment_gateway_factory: PaymentGatewayFactory
    
    async def _get_gateway_instance(self, gateway_type):
        gateway = await self.get_by_type(gateway_type)
        return self.payment_gateway_factory(gateway)
```

**10. Strategy Pattern**
- Payment gateway strategies
- Referral reward strategies (AMOUNT/PERCENT)
- Traffic limit strategies (NO_RESET/DAY/WEEK/MONTH)
- Partner accrual strategies (ON_FIRST_PAYMENT/ON_EACH_PAYMENT)

### **2.3 Request Flow Examples**

**User Starts Bot (New User with Referral):**
```
1. /start?start=ref_ABC123
   ↓
2. TelegramWebhookEndpoint._handle_request()
   ↓
3. Dispatcher.feed_update()
   ↓
4. Middleware Chain:
   - ErrorMiddleware
   - AccessMiddleware
   - RulesMiddleware
   - UserMiddleware → Creates user, attaches referral
   - ChannelMiddleware
   - ThrottlingMiddleware
   ↓
5. on_start_command() handler
   ↓
6. ReferralService.handle_referral()
   ↓
7. Start MainMenu.MAIN dialog
```

**Subscription Purchase Flow:**
```
1. User clicks "Buy Subscription"
   ↓
2. Subscription dialog: PLANS → DURATION → DEVICE_TYPE → PAYMENT_METHOD → CONFIRM
   ↓
3. PaymentGatewayService.create_payment()
   ↓
4. User completes payment
   ↓
5. Payment gateway webhook → payments_webhook()
   ↓
6. Gateway.handle_webhook()
   ↓
7. handle_payment_transaction_task.kiq()
   ↓
8. PaymentGatewayService.handle_payment_succeeded()
   ↓
9. purchase_subscription_task.kiq()
   ↓
10. Create/update user in Remnawave, create subscription
```

---

## **3. Services Layer**

### **3.1 Service Catalog (15 Services)**

| Service | File | Lines | Scope | Key Responsibilities |
|---------|------|-------|-------|---------------------|
| **UserService** | `user.py` | ~500 | REQUEST | User CRUD, profile sync, role management, discounts, points, search |
| **SubscriptionService** | `subscription.py` | ~350 | REQUEST | Subscription CRUD, status management, trial handling, multi-subscription |
| **RemnawaveService** | `remnawave.py` | ~809 | REQUEST | Remnawave API integration, user provisioning, webhook handling |
| **PaymentGatewayService** | `payment_gateway.py` | ~400 | REQUEST | Payment creation, webhook coordination, transaction lifecycle |
| **PlanService** | `plan.py` | ~250 | REQUEST | Plan management, availability filtering, trial plans |
| **PromocodeService** | `promocode.py` | ~600 | REQUEST | Promocode CRUD, activation, reward application |
| **ReferralService** | `referral.py` | ~500 | REQUEST | Referral relationships, rewards, QR generation, points exchange |
| **PartnerService** | `partner.py` | ~814 | REQUEST | Partner accounts, 3-level commissions, withdrawals |
| **TransactionService** | `transaction.py` | ~150 | REQUEST | Transaction records, status tracking |
| **BroadcastService** | `broadcast.py` | ~250 | REQUEST | Broadcast campaigns, audience targeting |
| **BackupService** | `backup.py` | ~849 | APP | Database backup/restore, auto-backup scheduling |
| **NotificationService** | `notification.py` | ~400 | REQUEST | User/system notifications, message formatting |
| **SettingsService** | `settings.py` | ~300 | REQUEST | Bot configuration, access modes, notification toggles |
| **AuthService** | `auth.py` | ~200 | REQUEST | Username/password auth, JWT tokens |
| **AccessService** | `access.py` | ~250 | REQUEST | Access control, waitlist management |
| **PricingService** | `pricing.py` | ~100 | APP | Price calculations, discounts, currency rules |
| **ImporterService** | `importer.py` | ~150 | APP | 3X-UI user import |
| **WebhookService** | `webhook.py` | ~100 | APP | Telegram webhook setup |
| **CommandService** | `command.py` | ~100 | APP | Bot commands setup |

### **3.2 Service Dependencies**

```
                    ┌─────────────────┐
                    │  SettingsService│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│  UserService  │   │  PlanService  │   │GatewayService │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        │           ┌───────▼───────┐           │
        │           │SubscriptionSvc│           │
        │           └───────┬───────┘           │
        │                   │                   │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│ReferralService│   │RemnawaveService│  │TransactionSvc │
└───────┬───────┘   └───────────────┘   └───────────────┘
        │
┌───────▼───────┐
│PartnerService │
└───────────────┘

Independent Services:
- BroadcastService
- BackupService
- NotificationService
- PromocodeService
- ImporterService
- WebhookService
- AuthService
- AccessService
- PricingService
- CommandService
```

### **3.3 Key Service Implementations**

**UserService - Key Methods:**
```python
async def create(self, aiogram_user: AiogramUser) -> UserDto
async def get(self, telegram_id: int) -> Optional[UserDto]  # @redis_cache(ttl=TIME_1M)
async def update(self, user: UserDto) -> Optional[UserDto]
async def delete(self, user: UserDto) -> bool
async def compare_and_update(self, user: UserDto, aiogram_user: AiogramUser)
async def get_by_partial_name(self, query: str) -> list[UserDto]
async def get_by_referral_code(self, referral_code: str) -> Optional[UserDto]
async def set_block(self, user: UserDto, blocked: bool) -> None
async def set_role(self, user: UserDto, role: UserRole) -> None
async def add_points(self, user: UserDto, points: int) -> None
async def set_current_subscription(self, telegram_id: int, subscription_id: int)
```

**SubscriptionService - Key Methods:**
```python
async def create(self, user: UserDto, subscription: SubscriptionDto) -> SubscriptionDto
async def get(self, subscription_id: int) -> Optional[SubscriptionDto]
async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]
async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]
async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]
async def delete_subscription(self, subscription_id: int) -> bool
async def get_subscribed_users(self) -> list[UserDto]
async def get_expired_users(self) -> list[UserDto]
async def has_used_trial(self, user: UserDto) -> bool
static get_traffic_reset_delta(strategy: TrafficLimitStrategy) -> Optional[timedelta]
```

**RemnawaveService - Key Methods:**
```python
async def try_connection(self) -> None
async def create_user(self, user: UserDto, plan: PlanSnapshotDto) -> UserResponseDto
async def updated_user(self, user: UserDto, uuid: UUID, plan: PlanSnapshotDto, subscription: SubscriptionDto) -> UserResponseDto
async def delete_user(self, user: UserDto, uuid: Optional[UUID] = None) -> bool
async def get_devices_user(self, user: UserDto) -> list[HwidDeviceDto]
async def delete_device(self, user: UserDto, hwid: str) -> Optional[int]
async def sync_user(self, remna_user: RemnaUserDto, creating: bool = True) -> None
async def handle_user_event(self, event: str, remna_user: RemnaUserDto) -> None
async def handle_device_event(self, event: str, user: RemnaUserDto, device: HwidUserDeviceDto) -> None
async def handle_node_event(self, event: str, node: NodeDto) -> None
```

**PaymentGatewayService - Key Methods:**
```python
async def create_default(self) -> None
async def get(self, gateway_id: int) -> Optional[PaymentGatewayDto]
async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]
async def get_all(self, sorted: bool = False) -> list[PaymentGatewayDto]
async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]
async def create_payment(self, user, plan, pricing, purchase_type, gateway_type, ...) -> PaymentResult
async def handle_payment_succeeded(self, payment_id: UUID) -> None
async def handle_payment_canceled(self, payment_id: UUID) -> None
```

**ReferralService - Key Methods:**
```python
async def create_referral(self, referrer, referred, level) -> ReferralDto
async def get_referral_by_referred(self, telegram_id: int) -> Optional[ReferralDto]
async def get_referrals_by_referrer(self, telegram_id: int) -> List[ReferralDto]
async def get_referral_count(self, telegram_id: int) -> int
async def create_reward(self, referral_id, user_telegram_id, type, amount) -> ReferralRewardDto
async def handle_referral(self, user: UserDto, code: str) -> None
async def assign_referral_rewards(self, transaction: TransactionDto) -> None
async def get_ref_link(self, referral_code: str) -> str
def get_ref_qr(self, url: str) -> BufferedInputFile
```

**PartnerService - Key Methods:**
```python
async def create_partner(self, user: UserDto) -> PartnerDto
async def get_partner_by_user(self, telegram_id: int) -> Optional[PartnerDto]
async def is_partner(self, telegram_id: int) -> bool
async def add_partner_referral(self, partner, referral_telegram_id, level) -> PartnerReferralDto
async def handle_new_user_referral(self, user: UserDto, referrer_code: str) -> None
async def process_partner_earning(self, payer_user_id, payment_amount, gateway_type) -> None
async def request_withdrawal(self, partner, amount, method, requisites, settings) -> Optional[PartnerWithdrawalDto]
async def get_partner_statistics(self, partner: Optional[PartnerDto]) -> Dict[str, Any]
```

---

## **4. Database Layer**

### **4.1 Database Configuration**

| Setting | Value |
|---------|-------|
| **Database** | PostgreSQL 17 |
| **ORM** | SQLAlchemy 2.0 |
| **Migrations** | Alembic (28 migrations) |
| **Tables** | 18 |
| **Connection Pool** | 25 connections |
| **Max Overflow** | 25 |
| **Pool Timeout** | 10 seconds |
| **Pool Recycle** | 3600 seconds |

### **4.2 Table Schema**

**1. users**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR NULL,
    auth_username VARCHAR UNIQUE NULL,          -- For username/password auth
    password_hash VARCHAR NULL,                  -- bcrypt hash
    referral_code VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'USER',
    language VARCHAR NOT NULL DEFAULT 'ru',
    personal_discount INT DEFAULT 0,
    purchase_discount INT DEFAULT 0,
    points INT DEFAULT 0,
    is_blocked BOOLEAN DEFAULT FALSE,
    is_bot_blocked BOOLEAN DEFAULT FALSE,
    is_rules_accepted BOOLEAN DEFAULT TRUE,
    max_subscriptions INT NULL,
    current_subscription_id INT REFERENCES subscriptions(id),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**2. subscriptions**
```sql
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_remna_id UUID NOT NULL,
    user_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    status VARCHAR NOT NULL,
    is_trial BOOLEAN NOT NULL,
    traffic_limit INT NOT NULL,
    device_limit INT NOT NULL,
    internal_squads UUID[] NOT NULL,
    external_squad UUID,
    expire_at TIMESTAMP NOT NULL,
    url VARCHAR NOT NULL,
    device_type VARCHAR,
    plan JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**3. plans**
```sql
CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    tag VARCHAR,
    description TEXT,
    type VARCHAR NOT NULL,
    availability VARCHAR NOT NULL,
    traffic_limit INT NOT NULL,
    device_limit INT NOT NULL,
    subscription_count INT DEFAULT 1,
    order_index INT NOT NULL,
    is_active BOOLEAN NOT NULL,
    allowed_user_ids INT[],
    internal_squads UUID[] NOT NULL,
    external_squad UUID,
    traffic_limit_strategy VARCHAR DEFAULT 'no_reset',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**4. plan_durations**
```sql
CREATE TABLE plan_durations (
    id SERIAL PRIMARY KEY,
    plan_id INT REFERENCES plans(id) ON DELETE CASCADE,
    days INT NOT NULL
);
```

**5. plan_prices**
```sql
CREATE TABLE plan_prices (
    id SERIAL PRIMARY KEY,
    duration_id INT REFERENCES plan_durations(id) ON DELETE CASCADE,
    gateway_type VARCHAR NOT NULL,
    price INT NOT NULL,
    currency VARCHAR NOT NULL,
    discount INT DEFAULT 0
);
```

**6. transactions**
```sql
CREATE TABLE transactions (
    payment_id UUID PRIMARY KEY,
    user_telegram_id BIGINT REFERENCES users(telegram_id),
    status VARCHAR NOT NULL,
    purchase_type VARCHAR NOT NULL,
    gateway_type VARCHAR NOT NULL,
    pricing JSON NOT NULL,
    currency VARCHAR NOT NULL,
    plan JSON NOT NULL,
    renew_subscription_id INT,
    renew_subscription_ids INT[],
    device_types VARCHAR[],
    is_test BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**7. payment_gateways**
```sql
CREATE TABLE payment_gateways (
    id SERIAL PRIMARY KEY,
    order_index INT NOT NULL,
    type VARCHAR NOT NULL,
    currency VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL,
    settings JSON,  -- Encrypted
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**8. promocodes**
```sql
CREATE TABLE promocodes (
    id SERIAL PRIMARY KEY,
    code VARCHAR UNIQUE NOT NULL,
    reward_type VARCHAR NOT NULL,
    availability VARCHAR NOT NULL,
    reward INT NOT NULL,
    lifetime INT NOT NULL,
    max_activations INT NOT NULL,
    activation_count INT DEFAULT 0,
    is_active BOOLEAN NOT NULL,
    plan_id INT REFERENCES plans(id),
    plan_duration_days INT,
    allowed_user_ids INT[],
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**9. promocode_activations**
```sql
CREATE TABLE promocode_activations (
    id SERIAL PRIMARY KEY,
    promocode_id INT REFERENCES promocodes(id),
    user_telegram_id BIGINT NOT NULL,
    activated_at TIMESTAMP NOT NULL
);
```

**10. referrals**
```sql
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_telegram_id BIGINT NOT NULL,
    referred_telegram_id BIGINT UNIQUE NOT NULL,
    level INT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**11. referral_rewards**
```sql
CREATE TABLE referral_rewards (
    id SERIAL PRIMARY KEY,
    referral_id INT REFERENCES referrals(id),
    user_telegram_id BIGINT NOT NULL,
    type VARCHAR NOT NULL,
    amount INT NOT NULL,
    is_issued BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**12. partners**
```sql
CREATE TABLE partners (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT UNIQUE NOT NULL,
    balance INT DEFAULT 0,
    total_earned INT DEFAULT 0,
    total_withdrawn INT DEFAULT 0,
    referrals_count INT DEFAULT 0,
    level2_referrals_count INT DEFAULT 0,
    level3_referrals_count INT DEFAULT 0,
    individual_settings JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**13. partner_referrals**
```sql
CREATE TABLE partner_referrals (
    id SERIAL PRIMARY KEY,
    partner_id INT REFERENCES partners(id),
    referral_telegram_id BIGINT NOT NULL,
    level INT NOT NULL,
    parent_partner_id INT
);
```

**14. partner_transactions**
```sql
CREATE TABLE partner_transactions (
    id SERIAL PRIMARY KEY,
    partner_id INT REFERENCES partners(id),
    referral_telegram_id BIGINT NOT NULL,
    level INT NOT NULL,
    payment_amount INT NOT NULL,
    percent DECIMAL NOT NULL,
    earned_amount INT NOT NULL,
    source_transaction_id INT,
    description TEXT
);
```

**15. partner_withdrawals**
```sql
CREATE TABLE partner_withdrawals (
    id SERIAL PRIMARY KEY,
    partner_id INT REFERENCES partners(id),
    amount INT NOT NULL,
    status VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    requisites VARCHAR NOT NULL,
    admin_comment TEXT,
    processed_by BIGINT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**16. settings**
```sql
CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    access_mode VARCHAR NOT NULL,
    rules_required BOOLEAN DEFAULT FALSE,
    rules_link VARCHAR,
    channel_required BOOLEAN DEFAULT FALSE,
    channel_id VARCHAR,
    channel_link VARCHAR,
    channel_has_username BOOLEAN DEFAULT FALSE,
    default_currency VARCHAR NOT NULL,
    user_notifications JSON NOT NULL,
    system_notifications JSON NOT NULL,
    referral_settings JSON NOT NULL,
    partner_settings JSON NOT NULL,
    multi_subscription JSON NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**17. broadcasts**
```sql
CREATE TABLE broadcasts (
    id SERIAL PRIMARY KEY,
    task_id UUID UNIQUE NOT NULL,
    audience_type VARCHAR NOT NULL,
    plan_id INT,
    status VARCHAR NOT NULL,
    content JSON NOT NULL,
    buttons JSON,
    total_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**18. broadcast_messages**
```sql
CREATE TABLE broadcast_messages (
    id SERIAL PRIMARY KEY,
    broadcast_id INT REFERENCES broadcasts(id),
    user_id BIGINT NOT NULL,
    status VARCHAR NOT NULL,
    message_id INT,
    sent_at TIMESTAMP
);
```

### **4.3 Enumerations (50+)**

**UserRole:** DEV, ADMIN, USER

**SubscriptionStatus:** ACTIVE, DISABLED, LIMITED, EXPIRED, DELETED

**PlanType:** TRAFFIC, DEVICES, BOTH, UNLIMITED

**PlanAvailability:** ALL, NEW, EXISTING, INVITED, ALLOWED, TRIAL

**TransactionStatus:** PENDING, COMPLETED, CANCELED, REFUNDED, FAILED

**AccessMode:** PUBLIC, INVITED, PURCHASE_BLOCKED, REG_BLOCKED, RESTRICTED

**PaymentGatewayType:** TELEGRAM_STARS, YOOKASSA, YOOMONEY, CRYPTOMUS, HELEKET, CRYPTOPAY, ROBOKASSA, PAL24, WATA, PLATEGA

**Currency:** USD, XTR, RUB, USDT, TON, BTC, ETH, LTC

**PromocodeRewardType:** DURATION, TRAFFIC, DEVICES, SUBSCRIPTION, PERSONAL_DISCOUNT, PURCHASE_DISCOUNT

**ReferralRewardType:** POINTS, EXTRA_DAYS

**ReferralLevel:** FIRST, SECOND, THIRD

**PartnerLevel:** LEVEL_1, LEVEL_2, LEVEL_3

**PartnerAccrualStrategy:** ON_FIRST_PAYMENT, ON_EACH_PAYMENT

**WithdrawalStatus:** PENDING, COMPLETED, REJECTED, CANCELED

**BroadcastStatus:** PROCESSING, COMPLETED, CANCELED, DELETED, ERROR

**BroadcastAudience:** ALL, PLAN, SUBSCRIBED, UNSUBSCRIBED, EXPIRED, TRIAL

**DeviceType:** ANDROID, IPHONE, WINDOWS, MAC

**Locale:** AR, AZ, BE, CS, DE, EN, ES, FA, FR, HE, HI, ID, IT, JA, KK, KO, MS, NL, PL, PT, RO, RU, SR, TR, UK, UZ, VI

### **4.4 Repositories (9)**

| Repository | Key Methods |
|------------|-------------|
| **UserRepository** | get, get_by_ids, get_by_partial_name, get_by_referral_code, filter_by_role, filter_by_blocked, generate_unique_referral_code |
| **SubscriptionRepository** | get, get_by_remna_id, get_all_by_user, filter_by_plan_id |
| **PlanRepository** | get, get_by_name, get_by_tag, filter_active, filter_by_availability, get_max_index |
| **PromocodeRepository** | get, get_by_code, filter_by_type, filter_active |
| **TransactionRepository** | get, get_by_user, get_by_status, count, count_by_status |
| **PaymentGatewayRepository** | get, get_all, get_by_type |
| **ReferralRepository** | get_referral_by_referred, get_referrals_by_referrer, count_referrals_by_referrer, create_reward |
| **PartnerRepository** | get_partner_by_user, get_partner_by_id, create_partner, create_partner_referral, get_referrals_by_partner, create_transaction, create_withdrawal |
| **BroadcastRepository** | get, get_all, create, create_messages, update_message |

### **4.5 DTOs (25+)**

| DTO | Key Fields |
|-----|------------|
| **UserDto** | telegram_id, username, auth_username, role, language, personal_discount, purchase_discount, points, is_blocked, current_subscription |
| **SubscriptionDto** | user_remna_id, status, is_trial, traffic_limit, device_limit, internal_squads, external_squad, expire_at, url, device_type, plan |
| **PlanDto** | name, tag, type, availability, traffic_limit, device_limit, subscription_count, durations, allowed_user_ids, internal_squads, external_squad |
| **PlanSnapshotDto** | id, name, tag, type, traffic_limit, device_limit, duration, traffic_limit_strategy, internal_squads, external_squad |
| **TransactionDto** | payment_id, status, purchase_type, gateway_type, pricing, currency, plan, is_test |
| **PaymentGatewayDto** | order_index, type, currency, is_active, settings |
| **PromocodeDto** | code, reward_type, availability, reward, lifetime, max_activations, activation_count, is_active, plan |
| **ReferralDto** | referrer, referred, level |
| **ReferralRewardDto** | referral_id, user_telegram_id, type, amount, is_issued |
| **PartnerDto** | user_telegram_id, balance, total_earned, total_withdrawn, referrals_count, level2_referrals_count, level3_referrals_count, individual_settings, is_active |
| **PartnerReferralDto** | partner_id, referral_telegram_id, level, parent_partner_id |
| **PartnerTransactionDto** | partner_id, referral_telegram_id, level, payment_amount, percent, earned_amount |
| **PartnerWithdrawalDto** | partner_id, amount, status, method, requisites, admin_comment |
| **BroadcastDto** | task_id, audience_type, status, content, buttons, total_count, success_count, failed_count |
| **BroadcastMessageDto** | broadcast_id, user_id, status, message_id |
| **SettingsDto** | access_mode, rules_required, rules_link, channel_required, channel_id, default_currency, user_notifications, system_notifications, referral_settings, partner_settings, multi_subscription |
| **PriceDetailsDto** | original_amount, discount_percent, final_amount |
| **PaymentResult** | id, url |
| **AuthResult** | user, access_token, refresh_token |
| **ActivationResult** | success, error, promocode, message_key |

---

## **5. Bot Layer**

### **5.1 Bot Configuration**

| Setting | Value |
|---------|-------|
| **Framework** | aiogram 3.22.0 |
| **Dialog Management** | aiogram-dialog 2.4.0 |
| **Storage** | Redis (via RedisStorage) |
| **Key Builder** | DefaultKeyBuilder (with_bot_id, with_destiny) |

### **5.2 Middlewares (7)**

**1. ErrorMiddleware (OUTER)**
- Catches all exceptions
- Sends error notifications to devs
- Handles lost dialog context

**2. AccessMiddleware (OUTER)**
- Checks access mode (PUBLIC, INVITED, etc.)
- Blocks unauthorized users
- Manages waitlist for PURCHASE_BLOCKED mode

**3. RulesMiddleware (OUTER)**
- Enforces rules acceptance
- Shows rules keyboard if needed

**4. UserMiddleware (OUTER)**
- Loads/creates user from DB
- Syncs Telegram profile data
- Handles referral attachment
- Sets IS_NEW_USER, IS_SUPER_DEV flags

**5. ChannelMiddleware (OUTER)**
- Enforces channel subscription requirement
- Shows join channel keyboard

**6. ThrottlingMiddleware (OUTER)**
- Rate limiting (0.5s TTL cache)
- Prevents spam/flood

**7. GarbageMiddleware (INNER)**
- Auto-deletes non-/start messages

### **5.3 FSM State Groups (27)**

| State Group | States | Purpose |
|-------------|--------|---------|
| **MainMenu** | 16 | User main menu (main, devices, connect, invite, exchange) |
| **Subscription** | 16 | Subscription purchase flow (plans, duration, payment, confirm) |
| **Notification** | 1 | Close notification |
| **Dashboard** | 1 | Admin dashboard main |
| **DashboardStatistics** | 1 | Statistics overview |
| **DashboardBroadcast** | 7 | Broadcast management |
| **DashboardPromocodes** | 10 | Promocode configuration |
| **DashboardAccess** | 4 | Access control settings |
| **DashboardUsers** | 5 | User search and lists |
| **DashboardUser** | 28 | Individual user management |
| **DashboardBackup** | 6 | Backup management |
| **RemnashopMultiSubscription** | 2 | Multi-subscription settings |
| **RemnashopBanners** | 4 | Banner management |
| **RemnashopReferral** | 18 | Referral settings |
| **RemnashopPartner** | 10 | Partner settings |
| **RemnashopGateways** | 5 | Gateway configuration |
| **RemnashopNotifications** | 3 | Notification toggles |
| **RemnashopPlans** | 18 | Plan configuration |
| **DashboardRemnawave** | 5 | Remnawave panel stats |
| **DashboardImporter** | 6 | User import from 3X-UI |
| **UserPartner** | 6 | User partner interface |

### **5.4 Bot Routers**

**User Routers:**
- `menu/` - Main user menu (devices, connect, invite, exchange)
- `subscription/` - Subscription purchase flow

**Admin Routers:**
- `dashboard/` - Admin dashboard
  - `access/` - Access control
  - `backup/` - Backup management
  - `broadcast/` - Broadcast messaging
  - `importer/` - User import
  - `promocodes/` - Promocode management
  - `remnashop/` - Shop settings
    - `banners/` - Banner management
    - `gateways/` - Gateway config
    - `multisubscription/` - Multi-sub settings
    - `notifications/` - Notification settings
    - `partner/` - Partner settings
    - `plans/` - Plan configuration
    - `referral/` - Referral settings
  - `remnawave/` - Remnawave stats
  - `statistics/` - Statistics dashboard
  - `users/` - User management

**Extra Routers:**
- `extra/` - Additional features

### **5.5 Bot Widgets**

| Widget | Purpose |
|--------|---------|
| **Banner** | Locale-aware banner with fallback |
| **I18nFormat** | Translation with nested key support |
| **IgnoreUpdate** | Suppress message updates |

### **5.6 Bot Keyboards**

**Inline Keyboards:**
- `get_user_keyboard()` - Go to user profile button
- `get_channel_keyboard()` - Channel subscription
- `get_rules_keyboard()` - Rules acceptance
- `get_contact_support_keyboard()` - Support contact
- `get_remnashop_keyboard()` - GitHub, Telegram, donate
- `get_renew_keyboard()` - Renew subscription

---

## **6. API Layer**

### **6.1 FastAPI Configuration**

| Setting | Value |
|---------|-------|
| **Framework** | FastAPI 0.120.2+ |
| **Server** | uvicorn 0.38.0+ |
| **CORS** | Configured origins, credentials |
| **DI Integration** | dishka FastAPI provider |

### **6.2 Webhook Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/telegram` | POST | Telegram webhook (secret token verification) |
| `/api/v1/payments/{gateway}` | POST | Payment gateway webhooks (7 gateways) |
| `/api/v1/remnawave` | POST | Remnawave panel webhooks (signature verification) |

### **6.3 Authentication Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/register` | POST | Register with username/password |
| `/api/v1/auth/login` | POST | Login with username/password |
| `/api/v1/auth/telegram` | POST | Telegram OAuth authentication |
| `/api/v1/auth/refresh` | POST | Refresh JWT token |
| `/api/v1/auth/logout` | POST | Logout user |

### **6.4 User Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/user/me` | GET | Get current user |

### **6.5 Subscription Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/subscription/list` | GET | List user subscriptions |
| `/api/v1/subscription/{id}` | GET | Get subscription details |
| `/api/v1/subscription/purchase` | POST | Purchase subscription |
| `/api/v1/subscription/{id}/renew` | POST | Renew subscription |
| `/api/v1/subscription/{id}` | DELETE | Delete subscription |

### **6.6 Other Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/plans` | GET | List available plans |
| `/api/v1/promocode/activate` | POST | Activate promocode |
| `/api/v1/referral/info` | GET | Get referral information |
| `/api/v1/partner/info` | GET | Get partner information |
| `/api/v1/devices` | GET | List devices |
| `/api/v1/devices/generate` | POST | Generate device link |
| `/api/v1/devices/{hwid}` | DELETE | Revoke device |

---

## **7. Payment Gateways**

### **7.1 Gateway Overview**

| Gateway | Type | Currency | Status | IP Whitelist |
|---------|------|----------|--------|--------------|
| **Telegram Stars** | Native | XTR | ✅ Implemented | N/A |
| **YooKassa** | Russian Fiat | RUB | ✅ Implemented | 7 networks |
| **CryptoPay** | Crypto | USDT, TON, BTC, etc. | ✅ Implemented | N/A |
| **Heleket** | Crypto | USD | ✅ Implemented | N/A |
| **Pal24 (PayPalych)** | SBP/Cards | RUB | ✅ Implemented | N/A |
| **Platega** | Multi-method | RUB | ✅ Implemented | N/A |
| **WATA** | Multi-method | RUB | ✅ Implemented | N/A |
| YooMoney | Russian Fiat | RUB | ⚠️ Commented out | - |
| Cryptomus | Crypto | USD | ⚠️ Commented out | - |
| Robokassa | Russian Fiat | RUB | ⚠️ Commented out | - |

### **7.2 Gateway Base Class**

```python
class BasePaymentGateway(ABC):
    gateway: PaymentGatewayDto
    bot: Bot
    NETWORKS: list[str] = []  # IP whitelist for webhooks

    @abstractmethod
    async def handle_create_payment(amount: Decimal, details: str) -> PaymentResult: ...

    @abstractmethod
    async def handle_webhook(request: Request) -> tuple[UUID, TransactionStatus]: ...

    def _is_ip_trusted(self, ip: str) -> bool:
        return any(self._is_ip_in_network(ip, net) for net in self.NETWORKS)
```

### **7.3 Gateway Implementations**

**Telegram Stars:**
- Uses `bot.create_invoice_link()`
- No external API needed
- Handled via `pre_checkout_query`

**YooKassa:**
- API: `https://api.yookassa.ru/v3/payments`
- IP whitelist: 7 networks (185.71.76.0/27, etc.)
- 54-FZ receipt support
- VAT code configuration

**CryptoPay (CryptoBot):**
- API: `https://pay.crypt.bot/api`
- Currencies: USDT, TON, BTC, ETH, LTC, BNB, TRX, USDC
- 1-hour invoice expiration
- Webhook signature verification

**Heleket:**
- API: `https://api.heleket.com/v1`
- SHA256 signature verification
- Invoice creation

**Pal24 (PayPalych):**
- API: `https://paypalych.com/api/v1`
- SBP and card payments
- Signature verification

**Platega:**
- API: `https://app.platega.io`
- Multiple payment methods
- Description sanitization

**WATA:**
- API: `https://api.wata.pro/api`
- Link expiration (60 minutes)
- Transaction search

### **7.4 Payment Flow**

```
1. User selects plan → duration → device type
   ↓
2. PaymentGatewayService.create_payment()
   - Calculate pricing (with discounts)
   - Create transaction (PENDING)
   - Call gateway.handle_create_payment()
   ↓
3. User pays at gateway
   ↓
4. Gateway sends webhook → /api/v1/payments/{gateway}
   ↓
5. payments_webhook()
   - Get gateway instance
   - Call gateway.handle_webhook()
   - Verify signature/IP
   ↓
6. handle_payment_transaction_task.kiq(payment_id, status)
   ↓
7. PaymentGatewayService.handle_payment_succeeded()
   - Update transaction (COMPLETED)
   - purchase_subscription_task.kiq()
   - Assign referral rewards
   - Process partner earnings
   ↓
8. purchase_subscription_task()
   - Create/update user in Remnawave
   - Create subscription
   - Send success notification
```

---

## **8. Background Tasks**

### **8.1 Taskiq Configuration**

| Setting | Value |
|---------|-------|
| **Broker** | Taskiq Redis (streams) |
| **Worker** | Separate container |
| **Scheduler** | Separate container |
| **Middlewares** | Error handling middleware |

### **8.2 Background Tasks (16+)**

| Task | Schedule | Purpose |
|------|----------|---------|
| `purchase_subscription_task` | On-demand | Process successful payments |
| `handle_payment_transaction_task` | On-demand | Handle payment webhooks |
| `send_user_notification_task` | On-demand | User notifications (batched) |
| `send_system_notification_task` | On-demand | System notifications |
| `send_error_notification_task` | On-demand | Error alerts to devs |
| `send_subscription_expire_notification_task` | On-demand | Expiration reminders |
| `send_subscription_limited_notification_task` | On-demand | Traffic limit alerts |
| `give_referrer_reward_task` | On-demand | Issue referral rewards |
| `assign_referral_rewards_task` | On-demand | Assign rewards after payment |
| `process_partner_earning_task` | On-demand | Partner commission processing |
| `cleanup_expired_subscriptions_task` | Cron 0 3 * * * | Scheduled cleanup |
| `check_bot_update` | On startup | Check for bot updates |
| `redirect_to_successed_payment_task` | On-demand | Payment success redirects |
| `send_access_opened_notifications_task` | On-demand | Access granted notifications |
| `send_test_transaction_notification_task` | On-demand | Test payment confirmations |
| `delete_current_subscription_task` | On-demand | Subscription deletion |
| `update_status_current_subscription_task` | On-demand | Update subscription status |
| `cancel_transaction_task` | Cron */30 * * * * | Cancel old pending transactions |
| `trial_subscription_task` | On-demand | Trial subscription creation |

### **8.3 Task Scheduler**

**Scheduled Tasks:**
- `*/30 * * * *` - Cancel old pending transactions
- `0 3 * * *` - Daily cleanup at 03:00

---

## **9. Frontend Web App**

### **9.1 Technology Stack**

| Category | Technology | Version |
|----------|-----------|---------|
| **Framework** | React | 19.2.4 |
| **Language** | TypeScript | 5.7.0 |
| **Build Tool** | Vite | 6.0.0 |
| **Styling** | TailwindCSS | 4.0.0 |
| **UI Library** | Radix UI | Latest |
| **State** | Zustand | 5.0.0 |
| **Data Fetching** | TanStack Query | 5.60.0 |
| **Routing** | React Router | 7.0.0 |
| **Forms** | React Hook Form + Zod | 4.50 + 3.24 |
| **HTTP** | Axios | 1.7.0 |
| **Icons** | Lucide React | 0.460.0 |
| **Notifications** | Sonner | 2.0.0 |

### **9.2 Pages (10)**

| Page | Route | Purpose |
|------|-------|---------|
| **LandingPage** | `/` | Landing page with features, pricing, CTA |
| **LoginPage** | `/auth/login` | Username/password login |
| **RegisterPage** | `/auth/register` | Registration with Telegram ID |
| **DashboardPage** | `/dashboard` | Main dashboard with stats |
| **SubscriptionPage** | `/dashboard/subscription` | View/manage subscriptions |
| **PurchasePage** | `/dashboard/subscription/purchase` | Buy new subscription |
| **DevicesPage** | `/dashboard/devices` | Manage connected devices |
| **ReferralsPage** | `/dashboard/referrals` | Referral stats and link |
| **PromocodesPage** | `/dashboard/promocodes` | Activate promocodes |
| **PartnerPage** | `/dashboard/partner` | Partner earnings and withdrawals |
| **SettingsPage** | `/dashboard/settings` | User settings |

### **9.3 Components (27)**

**Layout (4):**
- `DashboardLayout` - Main dashboard layout
- `Header` - Top navigation
- `Sidebar` - Side navigation
- `MobileNav` - Mobile navigation drawer

**Auth (4):**
- `AuthProvider` - Auth context provider
- `ProtectedRoute` - Route guard for authenticated users
- `PublicRoute` - Route guard for unauthenticated users
- `TelegramLogin` - Telegram OAuth widget

**UI (19):**
- `Alert`, `Avatar`, `Badge`, `Button`, `Card`
- `Dialog`, `DropdownMenu`, `Input`, `Label`
- `Progress`, `RadioGroup`, `Select`, `Sheet`
- `Skeleton`, `Switch`, `Tabs`, `Textarea`
- `Toast`, `Tooltip`

### **9.4 API Client**

```typescript
const api = {
  auth: {
    login: (username, password) => POST /auth/login,
    register: (telegram_id, username, password) => POST /auth/register,
    telegram: (initData, ...) => POST /auth/telegram,
    refresh: (refreshToken) => POST /auth/refresh,
    logout: () => POST /auth/logout,
  },
  user: { me: () => GET /user/me },
  subscription: {
    list: () => GET /subscription/list,
    get: (id) => GET /subscription/{id},
    purchase: (data) => POST /subscription/purchase,
    renew: (id, data) => POST /subscription/{id}/renew,
    delete: (id) => DELETE /subscription/{id},
  },
  plans: { list: () => GET /plans },
  promocode: { activate: (code) => POST /promocode/activate },
  referral: {
    info: () => GET /referral/info,
    list: (page, limit) => GET /referral/list,
  },
  partner: {
    info: () => GET /partner/info,
    earnings: (page, limit) => GET /partner/earnings,
    withdraw: (data) => POST /partner/withdraw,
    withdrawals: () => GET /partner/withdrawals,
  },
  devices: {
    list: (subscriptionId) => GET /devices?subscription_id={id},
    generate: (subscriptionId) => POST /devices/generate,
    revoke: (hwid) => DELETE /devices/{hwid},
  },
}
```

### **9.5 Authentication**

**JWT Configuration:**
- Access token: 7 days (604800 seconds)
- Refresh token: 30 days
- Algorithm: HS256
- Secret: `WEB_APP_JWT_SECRET` (min 32 chars)

**Auth Flow:**
```
1. User enters credentials
   ↓
2. POST /api/v1/auth/login or /auth/register
   ↓
3. Server validates and returns JWT tokens
   ↓
4. Store tokens in localStorage
   ↓
5. Add Authorization header to all requests
   ↓
6. On 401, try refresh token
   ↓
7. If refresh fails, redirect to login
```

---

## **10. Infrastructure**

### **10.1 Dependency Injection**

**Container Setup:**
```python
def create_container(config: AppConfig, bg_manager_factory: BgManagerFactory) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
    }
    container = make_async_container(*get_providers(), FastapiProvider(), context=context)
    return container
```

**Providers:**
- `ConfigProvider` - AppConfig
- `BotProvider` - Bot instance
- `DatabaseProvider` - Engine, session_pool
- `RedisProvider` - Redis client
- `RemnawaveProvider` - RemnawaveSDK
- `ServicesProvider` - All 15 services
- `I18nProvider` - TranslatorHub
- `PaymentGatewaysProvider` - Gateway factory

### **10.2 Redis Integration**

**Usage:**
- FSM storage (aiogram)
- User data caching (1 minute TTL)
- Settings caching (10 minutes TTL)
- Blocked users caching (10 minutes TTL)
- Access waitlist
- Recent registered users
- Recent activity users
- Taskiq broker

**Key Structure:**
```python
class StorageKey(BaseModel):
    prefix: str
    parts: list[str]
    
    def pack(self) -> str:
        # "prefix:part1:part2:value"
        ...

# Examples
"cache:get_user:123456"
"cache:get_blocked_users"
"cache:users_count"
"access_wait_list"
"recent_registered_users"
"recent_activity_users"
```

### **10.3 Taskiq Integration**

**Broker Setup:**
```python
broker = TaskiqRedisBroker(
    redis_url=config.redis.dsn,
    queue_name="altshop",
)
```

**Middlewares:**
- `ErrorMiddleware` - Error notification to devs

---

## **11. Configuration**

### **11.1 Environment Variables (60+)**

**App Configuration:**
- `APP_DOMAIN` - Public domain (no protocol, no trailing slash)
- `APP_HOST` - Server host (0.0.0.0)
- `APP_PORT` - Server port (5000)
- `APP_LOCALES` - Supported locales (ru,en)
- `APP_DEFAULT_LOCALE` - Default locale (ru)
- `APP_CRYPT_KEY` - Fernet encryption key (44 char Base64)
- `APP_ORIGINS` - CORS origins (comma-separated)

**Bot Configuration:**
- `BOT_TOKEN` - Telegram Bot API token
- `BOT_SECRET_TOKEN` - Webhook secret token
- `BOT_DEV_ID` - Developer Telegram user ID (comma-separated)
- `BOT_SUPPORT_USERNAME` - Support username
- `BOT_MINI_APP` - Mini app URL or false
- `BOT_RESET_WEBHOOK` - Reset webhook on shutdown
- `BOT_DROP_PENDING_UPDATES` - Drop pending updates
- `BOT_SETUP_COMMANDS` - Setup bot commands
- `BOT_USE_BANNERS` - Enable banners
- `BOT_SETUP_WEBHOOK` - Setup webhook on startup

**Web App Configuration:**
- `WEB_APP_ENABLED` - Enable web app
- `WEB_APP_URL` - Web app URL
- `WEB_APP_JWT_SECRET` - JWT secret (min 32 chars)
- `WEB_APP_JWT_EXPIRY` - JWT expiry (seconds, default 604800)
- `WEB_APP_CORS_ORIGINS` - CORS origins
- `WEB_APP_JWT_REFRESH_ENABLED` - Enable token refresh
- `WEB_APP_API_SECRET_TOKEN` - API secret token
- `WEB_APP_RATE_LIMIT_ENABLED` - Enable rate limiting
- `WEB_APP_RATE_LIMIT_MAX_REQUESTS` - Max requests per minute
- `WEB_APP_RATE_LIMIT_WINDOW` - Rate limit window (seconds)

**Remnawave Configuration:**
- `REMNAWAVE_HOST` - Remnawave hostname
- `REMNAWAVE_PORT` - Remnawave port (3000)
- `REMNAWAVE_TOKEN` - API token
- `REMNAWAVE_WEBHOOK_SECRET` - Webhook secret
- `REMNAWAVE_CADDY_TOKEN` - Caddy API key
- `REMNAWAVE_COOKIE` - Custom cookie

**Database Configuration:**
- `DATABASE_HOST` - PostgreSQL host
- `DATABASE_PORT` - PostgreSQL port (5432)
- `DATABASE_NAME` - Database name
- `DATABASE_USER` - Database user
- `DATABASE_PASSWORD` - Database password
- `DATABASE_ECHO` - Echo SQL queries
- `DATABASE_ECHO_POOL` - Echo pool operations
- `DATABASE_POOL_SIZE` - Pool size (25)
- `DATABASE_MAX_OVERFLOW` - Max overflow (25)
- `DATABASE_POOL_TIMEOUT` - Pool timeout (10)
- `DATABASE_POOL_RECYCLE` - Pool recycle (3600)

**Redis Configuration:**
- `REDIS_HOST` - Redis host
- `REDIS_PORT` - Redis port (6379)
- `REDIS_NAME` - Redis database index (0)
- `REDIS_PASSWORD` - Redis password

**Backup Configuration:**
- `BACKUP_AUTO_ENABLED` - Enable auto backups
- `BACKUP_INTERVAL_HOURS` - Backup interval (24)
- `BACKUP_TIME` - Backup time (03:00)
- `BACKUP_MAX_KEEP` - Max backups to keep (7)
- `BACKUP_COMPRESSION` - Enable compression
- `BACKUP_INCLUDE_LOGS` - Include logs
- `BACKUP_LOCATION` - Backup directory
- `BACKUP_SEND_ENABLED` - Send to Telegram
- `BACKUP_SEND_CHAT_ID` - Telegram chat ID
- `BACKUP_SEND_TOPIC_ID` - Forum topic ID

### **11.2 Configuration Validation**

```python
class AppConfig(BaseConfig, env_prefix="APP_"):
    domain: SecretStr
    host: str = "0.0.0.0"
    port: int = 5000
    locales: LocaleList = LocaleList([Locale.EN])
    default_locale: Locale = Locale.EN
    crypt_key: SecretStr
    
    @field_validator("domain")
    def validate_domain(cls, field: SecretStr) -> SecretStr:
        if not re.match(DOMAIN_REGEX, field.get_secret_value()):
            raise ValueError("APP_DOMAIN has invalid format")
        return field
    
    @field_validator("crypt_key")
    def validate_crypt_key(cls, field: SecretStr) -> SecretStr:
        if not re.match(r"^[A-Za-z0-9+/=]{44}$", field.get_secret_value()):
            raise ValueError("APP_CRYPT_KEY must be a valid 44-character Base64 string")
        return field
```

---

## **12. Security**

### **12.1 Authentication**

**Username/Password:**
- bcrypt hashing (12 rounds)
- JWT access token (7 days)
- JWT refresh token (30 days)
- HS256 algorithm

**Telegram OAuth:**
- Telegram Login Widget
- initData validation
- JWT token issuance

**Telegram Mini App:**
- Automatic authentication via `initData`
- WebApp SDK integration

### **12.2 Authorization**

**User Roles:**
- `DEV` - Full access (BOT_DEV_ID)
- `ADMIN` - Dashboard access
- `USER` - Standard features

**Access Modes:**
- `PUBLIC` - Open to all
- `INVITED` - Referral only
- `PURCHASE_BLOCKED` - No purchases
- `REG_BLOCKED` - No new registrations
- `RESTRICTED` - Complete lockdown

### **12.3 Data Protection**

**Encryption:**
- Fernet encryption for sensitive data
- Payment gateway credentials encrypted
- API keys encrypted
- Tokens encrypted

**Webhook Verification:**
- Telegram: Secret token comparison
- Remnawave: Signature verification
- Payment gateways: IP whitelisting + signature

**Rate Limiting:**
- TTL cache (0.5s, 10K max)
- Per-user throttling

**CORS:**
- Configured origins
- Credentials support
- All methods/headers allowed

---

## **13. Internationalization**

### **13.1 Configuration**

| Setting | Value |
|---------|-------|
| **Library** | fluentogram 1.2.1 |
| **Format** | FTL (Fluent) |
| **Supported Locales** | 26 defined, 2 active (ru, en) |
| **Translation Files** | 4 per locale (buttons, messages, notifications, utils) |
| **Translation Keys** | 500+ |

### **13.2 Translation Structure**

```
assets/translations/
├── ru/
│   ├── buttons.ftl
│   ├── messages.ftl (2340 lines)
│   ├── notifications.ftl
│   └── utils.ftl
└── en/
    ├── buttons.ftl
    ├── messages.ftl
    ├── notifications.ftl
    └── utils.ftl
```

### **13.3 Features**

- Locale-aware banners
- Fluent pluralization rules
- Variable interpolation
- HTML support
- Nested key support

---

## **14. Deployment**

### **14.1 Docker Services (7)**

| Service | Image | Purpose |
|---------|-------|---------|
| `altshop-nginx` | nginx:1.28 | SSL reverse proxy |
| `altshop-db` | postgres:17 | PostgreSQL database |
| `altshop-redis` | valkey/valkey:9-alpine | Redis cache & queue |
| `altshop` | altshop:local | Main bot application |
| `altshop-taskiq-worker` | altshop:local | Background task worker |
| `altshop-taskiq-scheduler` | altshop:local | Task scheduler |
| `webapp-build` | node:20-alpine | React build service |

### **14.2 Nginx Configuration**

**Features:**
- SSL termination (TLS 1.2/1.3)
- HTTP/2 support
- Gzip compression
- WebSocket support
- Static file serving
- API proxying
- CORS headers

**Locations:**
- `/` - Landing page
- `/webapp/` - Mini app
- `/assets/` - Static assets (1 year cache)
- `/api/v1` - Backend API
- `/telegram` - Telegram webhook
- `/remnawave` - Remnawave webhook
- `/payments` - Payment webhooks

### **14.3 Health Checks**

All services have health checks:
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- Nginx: PID file check

---

## **15. Known Issues & Technical Debt**

### **15.1 Commented Dependencies**

```toml
# Commented out in pyproject.toml
# remnawave @ file:///opt/python-sdk/remnawave
# remnawave @ git+https://github.com/remnawave/python-sdk.git@development
```

**Payment Gateways Commented:**
- YooMoney
- Cryptomus
- Robokassa

### **15.2 Legacy Peer Dependencies**

```bash
npm install --legacy-peer-deps
```
Indicates potential dependency conflicts in web app.

### **15.3 Bundle Size**

Web app bundle >500KB. Could benefit from:
- Code splitting optimization
- Lazy loading
- Tree shaking improvements

### **15.4 Hardcoded Texts**

Some landing page texts not in i18n. Should use translations for consistency.

### **15.5 Windows Line Endings**

`docker-entrypoint.sh` has CRLF conversion logic, indicating potential cross-platform issues.

### **15.6 SDK Validation Issues**

Remnawave SDK has DTO validation problems with `subscriptionSettings`. Workaround implemented with raw HTTP fallback.

### **15.7 Migration Count**

28 migrations suggest rapid development. May benefit from consolidation.

### **15.8 Test Coverage**

Limited visible test files. Could benefit from:
- Unit tests for services
- Integration tests
- E2E tests

---

## **16. Areas Requiring Further Study**

### **16.1 Not Fully Studied Files**

**Bot Routers (Dashboard Sub-folders):**
- [ ] `dashboard/access/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/backup/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/broadcast/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/importer/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/promocodes/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/banners/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/gateways/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/multisubscription/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/notifications/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/partner/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/plans/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnashop/referral/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/remnawave/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/statistics/dialog.py`, `getters.py`, `handlers.py`
- [ ] `dashboard/users/dialog.py`, `getters.py`, `handlers.py`

**Payment Gateways:**
- [ ] `heleket.py`
- [ ] `pal24.py`
- [ ] `platega.py`
- [ ] `wata.py`

**Taskiq Tasks:**
- [ ] `broadcast.py`
- [ ] `importer.py`
- [ ] `redirects.py`
- [ ] `updates.py`

**Repositories:**
- [ ] `broadcast.py`
- [ ] `partner.py` (full)
- [ ] `payment_gateway.py`
- [ ] `plan.py` (full)
- [ ] `promocode.py` (full)
- [ ] `referral.py` (full)
- [ ] `settings.py`
- [ ] `subscription.py` (full)
- [ ] `transaction.py` (full)

**SQL Models:**
- [ ] `partner.py`
- [ ] `promocode.py`
- [ ] `referral.py`
- [ ] `broadcast.py`
- [ ] `settings.py`
- [ ] `transaction.py`
- [ ] `plan.py` (full)

**DTOs:**
- [ ] `broadcast.py`
- [ ] `partner.py`
- [ ] `payment_gateway.py`
- [ ] `promocode.py`
- [ ] `referral.py`
- [ ] `settings.py`
- [ ] `transaction.py`

**Migrations:**
- [ ] All 28 migration files (detailed review)

**Translations:**
- [ ] English translations
- [ ] `notifications.ftl`
- [ ] `utils.ftl`
- [ ] `buttons.ftl`

**Core Utilities:**
- [ ] `formatters.py`
- [ ] `generators.py`
- [ ] `iterables.py`
- [ ] `json_utils.py`
- [ ] `message_payload.py`
- [ ] `time.py`
- [ ] `validators.py`
- [ ] `types.py`

**Security:**
- [ ] `crypto.py`
- [ ] `jwt_handler.py`

**Bot Widgets:**
- [ ] `banner.py`
- [ ] `i18n_format.py`
- [ ] `ignore_update.py`

**Web App UI Components:**
- [ ] All 19 UI component files

### **16.2 Estimated Remaining Work**

| Category | Files | Estimated Lines |
|----------|-------|-----------------|
| Bot Routers | ~50 | ~10,000 |
| Payment Gateways | 4 | ~800 |
| Taskiq Tasks | 4 | ~400 |
| Repositories | ~9 | ~1,500 |
| SQL Models | ~7 | ~700 |
| DTOs | ~7 | ~500 |
| Migrations | 28 | ~1,400 |
| Translations | ~8 | ~4,000 |
| Core Utilities | ~8 | ~800 |
| Security | 2 | ~200 |
| Bot Widgets | 3 | ~300 |
| Web App Components | 19 | ~2,000 |
| **Total** | **~149** | **~22,600** |

### **16.3 Priority Areas for Further Study**

**High Priority:**
1. All dashboard router handlers (admin functionality)
2. Remaining payment gateway implementations
3. All repository implementations
4. All SQL model definitions

**Medium Priority:**
1. All Taskiq task implementations
2. All DTO definitions
3. Core utility functions
4. Security modules

**Low Priority:**
1. All migration files
2. Translation files
3. Bot widgets
4. Web app UI components

---

## **Document Status**

| Version | Date | Author | Status |
|---------|------|--------|--------|
| 5.3 | 2026-02-20 | Qwen Code | OPEN FOR IMPROVEMENT |

---

## **Next Steps for Codex 5.3**

1. **Review and validate** all sections for accuracy
2. **Fill in gaps** from Section 16 (Areas Requiring Further Study)
3. **Add diagrams** for complex flows
4. **Document API request/response examples**
5. **Add troubleshooting guide**
6. **Create quick reference cards** for common tasks
7. **Add performance benchmarks**
8. **Document monitoring and alerting setup**

---

**This codex is a living document. Contributions and improvements are welcome!**

---

## **17. Codex Collaborative Addendum (v5.4)**

### **17.1 Review Metadata**

- Review date: **February 20, 2026**
- Reviewer: **Codex**
- Method: Independent static verification against source files (no runtime code mutations)

### **17.2 Scope Covered**

- Backend API routes and auth flows
- Frontend API contract usage
- Payment webhook and gateway verification paths
- Redis/cache behavior and key invalidation
- Infra/security posture in repository artifacts and config usage
- Documentation-to-code consistency checks

### **17.3 Confirmed with Qwen**

- Core webhook routes exist and are mounted for payments/remnawave/telegram integration:
  `src/api/app.py:20`, `src/api/app.py:21`, `src/api/app.py:28`.
- Remnawave webhook signature validation is implemented:
  `src/api/endpoints/remnawave.py:31`, `src/api/endpoints/remnawave.py:35`.
- Payment gateway implementations exist for Telegram Stars, YooKassa, CryptoPay, Heleket, Pal24, Platega, WATA:
  `src/infrastructure/payment_gateways/telegram_stars.py:1`,
  `src/infrastructure/payment_gateways/yookassa.py:1`,
  `src/infrastructure/payment_gateways/cryptopay.py:1`,
  `src/infrastructure/payment_gateways/heleket.py:1`,
  `src/infrastructure/payment_gateways/pal24.py:1`,
  `src/infrastructure/payment_gateways/platega.py:1`,
  `src/infrastructure/payment_gateways/wata.py:1`.
- The project still reflects layered DI + service + repository architecture:
  `src/infrastructure/di/ioc.py:1`,
  `src/infrastructure/database/uow.py:1`,
  `src/services/user.py:1`.

---

## **18. Consensus vs Disagreement Matrix**

| Severity | Topic | Qwen Claim (with line ref) | Codex Finding | Evidence (file:line list) | Status |
|----------|-------|-----------------------------|---------------|----------------------------|--------|
| Critical | Auth endpoint mismatch | `/api/v1/auth/register` and `/api/v1/auth/login` documented as active (`docs/QWEM_CODEX_TEAMS.md:1070`, `docs/QWEM_CODEX_TEAMS.md:1071`) | Username/password login/register are mounted under `/auth/*`, while `/api/v1/auth/*` covers Telegram web auth endpoints. | `docs/QWEM_CODEX_TEAMS.md:1070`, `docs/QWEM_CODEX_TEAMS.md:1071`, `src/api/endpoints/auth.py:11`, `src/api/endpoints/auth.py:34`, `src/api/endpoints/auth.py:63`, `src/api/endpoints/web_auth.py:28` | Disagreement logged (Codex verified) |
| Critical | `/api/v1/user/me` contract | `/api/v1/user/me` listed as user endpoint (`docs/QWEM_CODEX_TEAMS.md:1080`) | Current backend exposes `/api/v1/auth/me`; frontend calls `/user/me` under base `/api/v1`, causing contract mismatch with documented and implemented routes. | `docs/QWEM_CODEX_TEAMS.md:1080`, `src/api/endpoints/web_auth.py:391`, `web-app/src/lib/api.ts:118` | Disagreement logged (Codex verified) |
| Critical | Missing backend API surface vs frontend contract | Broad `/api/v1/*` resources documented and implied for web dashboard flows | Frontend expects subscription/plans/referral/partner/devices endpoints, but current endpoint package exports only payments/remnawave/telegram-web-auth routers (plus separate `/auth` router mount). | `web-app/src/lib/api.ts:123`, `web-app/src/lib/api.ts:132`, `web-app/src/lib/api.ts:142`, `src/api/endpoints/__init__.py:1`, `src/api/endpoints/__init__.py:2`, `src/api/endpoints/__init__.py:3` | Disagreement logged (Codex verified) |
| High | Dual JWT/auth systems | Unified auth behavior implied in current auth section | Two token systems coexist with different secrets/claims: `jwt_handler` uses `web_app.jwt_secret`, while `web_auth` signs/validates via bot token. | `src/core/security/jwt_handler.py:48`, `src/core/security/jwt_handler.py:95`, `src/api/endpoints/web_auth.py:300`, `src/api/endpoints/web_auth.py:342` | Disagreement logged (Codex verified) |
| Critical | Payment webhook exception behavior | Payment flow is documented as verified and reliable | Generic exception path in payments webhook currently falls through to `HTTP 200`, risking false acknowledgments to gateways on internal failures. | `src/api/endpoints/payments.py:53`, `src/api/endpoints/payments.py:71` | Disagreement logged (Codex verified) |
| High | Payment gateway verification consistency | "Payment gateways: IP whitelisting + signature" (`docs/QWEM_CODEX_TEAMS.md:1597`) | Verification is not uniformly mandatory across all gateway handlers; several parse payloads without enforced signature/IP checks. | `docs/QWEM_CODEX_TEAMS.md:1597`, `src/infrastructure/payment_gateways/cryptopay.py:103`, `src/infrastructure/payment_gateways/wata.py:112`, `src/infrastructure/payment_gateways/platega.py:118`, `src/infrastructure/payment_gateways/heleket.py:117`, `src/infrastructure/payment_gateways/pal24.py:118` | Disagreement logged (Codex verified) |
| High | User cache invalidation | Cache layer described as structured and stable | `users_count`/`get_all` cache invalidation path is inconsistent with declared cache prefixes, creating stale-count/list risk. | `src/services/user.py:179`, `src/services/user.py:197`, `src/services/user.py:367` | Disagreement logged (Codex verified) |
| Medium | Redis key cleanup strategy | Webhook lock management documented without caveat | Webhook lock cleanup uses Redis `KEYS` wildcard, which is a scale-risk pattern versus `SCAN`. | `src/services/webhook.py:79`, `src/services/webhook.py:80` | Disagreement logged (Codex verified) |
| High | `external_squad` type consistency | Plan/subscription model assumed coherent | Type mismatch persists: migration defines array UUID for plan field, while SQL model/DTO/web types treat it as singular UUID. | `src/infrastructure/database/migrations/versions/0011_extend_plans.py:33`, `src/infrastructure/database/models/sql/plan.py:60`, `src/infrastructure/database/models/dto/plan.py:91`, `web-app/src/types/index.ts:74` | Disagreement logged (Codex verified) |
| Critical | Sensitive TLS materials in repo | Security section does not flag committed key material | TLS key/cert files are present in repository tree and not explicitly ignored by `.gitignore`. | `nginx/remnabot_privkey.key`, `nginx/remnabot_fullchain.pem`, `nginx/nginx.conf:138`, `.gitignore:1` | Disagreement logged (Codex verified) |
| Medium | "Not fully studied" security files | `jwt_handler.py` and `crypto.py` marked unstudied (`docs/QWEM_CODEX_TEAMS.md:1827`, `docs/QWEM_CODEX_TEAMS.md:1828`) | Both files were reviewed in Codex pass and are no longer unstudied. | `docs/QWEM_CODEX_TEAMS.md:1827`, `docs/QWEM_CODEX_TEAMS.md:1828`, `src/core/security/jwt_handler.py:1`, `src/core/security/crypto.py:1` | Disagreement logged (Codex verified) |

---

## **19. Joint Prioritized Remediation Backlog**

| Priority | Owner | Workstream | Actions |
|----------|-------|------------|---------|
| P0 | Team | Auth + webhook correctness + key hygiene | Unify auth contract and token strategy; stop returning `HTTP 200` on internal webhook exceptions; remove committed TLS private key/cert artifacts and rotate exposed credentials. |
| P1 | Team | API contract + cache/redis reliability | Implement missing backend API surface (or align frontend calls to implemented routes); repair user cache invalidation keys; replace Redis `KEYS` with iterative `SCAN` cleanup. |
| P2 | Team | Config/runtime wiring + frontend behavior | Wire currently unused web-app security config fields into runtime logic; fix renew route/query mismatch in web app; replace stubbed/hardcoded dashboard/settings/devices behaviors with real API-backed flows. |

---

## **20. Coverage Delta vs Section 16**

| Previously Marked Unstudied | Codex Status | Evidence |
|-----------------------------|--------------|----------|
| `jwt_handler.py` | Reviewed | `docs/QWEM_CODEX_TEAMS.md:1828`, `src/core/security/jwt_handler.py:1` |
| `crypto.py` | Reviewed | `docs/QWEM_CODEX_TEAMS.md:1827`, `src/core/security/crypto.py:1` |
| Payment gateway files (`heleket.py`, `pal24.py`, `platega.py`, `wata.py`) | Reviewed | `src/infrastructure/payment_gateways/heleket.py:103`, `src/infrastructure/payment_gateways/pal24.py:104`, `src/infrastructure/payment_gateways/platega.py:118`, `src/infrastructure/payment_gateways/wata.py:112` |
| Taskiq subscriptions/payment flow areas | Reviewed (summary verified) | `src/infrastructure/taskiq/tasks/subscriptions.py:126`, `src/infrastructure/taskiq/tasks/subscriptions.py:607`, `src/infrastructure/taskiq/tasks/payments.py:14`, `src/infrastructure/taskiq/tasks/payments.py:28` |

---

## **21. Document Status Update**

### **21.1 Extended Status Table**

| Version | Date | Author | Status |
|---------|------|--------|--------|
| 5.3 | 2026-02-20 | Qwen Code | OPEN FOR IMPROVEMENT |
| 5.4 | 2026-02-20 | Codex | COLLABORATIVE ADDENDUM ADDED |
| 5.5 | 2026-02-20 | Codex | PARITY CLOSURE PASS IMPLEMENTED (CODE + BUILD VERIFIED) |

### **21.2 Collaboration Note**

1. Qwen baseline retained.
2. Codex disagreements are evidence-cited.
3. Conflicts should be resolved by code-first verification.

---

## **22. Codex Parity Verification & Closure (v5.5)**

### **22.1 Review Date**

- **February 20, 2026**

### **22.2 Implemented in This Pass (Code-Verified)**

**Backend contract updates**
- Added `GET /api/v1/plans` in `src/api/endpoints/user.py`.
- Added `POST /api/v1/subscription/{subscription_id}/renew` alias in `src/api/endpoints/user.py`.
- Implemented working `POST /api/v1/subscription/trial` flow in `src/api/endpoints/user.py`.
- Normalized purchase response to include both `payment_url` and compatibility alias `url` in `src/api/endpoints/user.py`.
- Fixed renew purchase snapshot creation to pass duration to `PlanSnapshotDto.from_plan(...)` in `src/api/endpoints/user.py`.
- Fixed runtime DTO field mapping bugs in referral/partner endpoints (`referrer`/`transaction` fields) to prevent 500s on non-empty datasets in `src/api/endpoints/user.py`.
- Fixed active subscription status comparison in promocode branching flow to use enum-safe value checks in `src/api/endpoints/user.py`.
- Fixed web registration for existing Telegram users: if `telegram_id` already exists without web credentials, backend now attaches `auth_username` + `password_hash` instead of returning hard failure (`src/services/auth.py`).

**Frontend parity fixes**
- Fixed API base path usage (removed double `/api/v1` prefix behavior) in `web-app/src/lib/api.ts`.
- Aligned frontend client types with backend wrappers (`subscriptions`, `referrals`, `partner`, `devices`) in:
  - `web-app/src/lib/api.ts`
  - `web-app/src/types/index.ts`
- Updated purchase flow to support renew route param and `payment_url`/`url` compatibility in `web-app/src/pages/dashboard/PurchasePage.tsx`.
- Updated dashboard/subscription/promocode queries to consume wrapped subscription list response:
  - `web-app/src/pages/dashboard/DashboardPage.tsx`
  - `web-app/src/pages/dashboard/SubscriptionPage.tsx`
  - `web-app/src/pages/dashboard/PromocodesPage.tsx`
- Updated referrals/partner/devices pages for actual response shapes and removed false-working UI paths:
  - `web-app/src/pages/dashboard/ReferralsPage.tsx` (exchange flow disabled until backend endpoints exist)
  - `web-app/src/pages/dashboard/PartnerPage.tsx`
  - `web-app/src/pages/dashboard/DevicesPage.tsx`
- Converted settings page to explicit read-only mode (no fake save/password simulation):
  - `web-app/src/pages/dashboard/SettingsPage.tsx`
- Fixed auth routing under `/webapp` deployment:
  - `BrowserRouter` now uses basename from Vite base (`web-app/src/App.tsx`).
  - hard redirects use app-base helper (`web-app/src/lib/app-path.ts`, `web-app/src/lib/api.ts`, `web-app/src/stores/auth-store.ts`, `web-app/src/components/auth/AuthProvider.tsx`).
  - register/login pages now surface backend `detail` messages instead of generic-only errors (`web-app/src/pages/auth/RegisterPage.tsx`, `web-app/src/pages/auth/LoginPage.tsx`).

**Data model compatibility**
- Extended subscription DTO with missing fields used by API serialization (`user_telegram_id`, `traffic_used`, `devices_count`) in `src/infrastructure/database/models/dto/subscription.py`.

**Deploy/404 fixes**
- Unified compose mounts from `./webapp/dist` to canonical `./web-app/dist` in `docker-compose.yml`.
- Updated ignore rules from `webapp/*` to `web-app/*` in `.gitignore`.
- Synced deploy guide commands and topology to actual runtime (`altshop-nginx`, static alias `/webapp/`, root redirect) in `docs/WEB_APP_NGINX_SETUP.md`.
- Hardened nginx SPA fallback in `nginx/nginx.conf` (`try_files $uri $uri/index.html /webapp/index.html`) to prevent `/webapp/*` 403/500 responses caused by bad fallback resolution.
- Set Vite base to `/webapp/` and favicon path to `%BASE_URL%vite.svg` to prevent root `/auth/*` escape and `/vite.svg` 404 noise in production (`web-app/vite.config.ts`, `web-app/index.html`).

**Resolved disagreements from v5.4 matrix (current state)**
- `/api/v1/auth/register` and `/api/v1/auth/login` are now explicitly served by `web_auth_router` in `src/api/endpoints/web_auth.py`.
- `/api/v1/user/me` is served by `user_router` in `src/api/endpoints/user.py`.
- Backend endpoint export surface includes `user_router` and `web_auth_router` in `src/api/endpoints/__init__.py`.

### **22.3 Validation Results**

- `python -m py_compile src/api/endpoints/user.py src/api/endpoints/web_auth.py src/api/app.py src/__main__.py src/infrastructure/database/models/dto/subscription.py` -> **PASS**
- `cd web-app && npm run type-check` -> **PASS**
- `cd web-app && npm run build` -> **PASS**
- External smoke check (2026-02-20): `curl -I https://remnabot.2get.pro/` -> **302** to `/webapp/`; `curl -I https://remnabot.2get.pro/webapp/index.html` -> **500** on current deployed instance (requires redeploy with updated nginx config and verified `dist` mount/permissions).

### **22.4 Remaining Gaps (Not Closed in This Pass)**

- Payment webhook exception policy (internal exception branch returning HTTP 200) still requires hardening.
- TLS private key/cert material in repository still requires rotation/removal policy.
- Referral/partner advanced business data remains partially stubbed by backend TODO markers.
- Production server still needs deployment of latest `nginx/nginx.conf` and static build artifacts to clear `/webapp/*` runtime 500 on the live host.

### **22.5 Document Status Extension**

| Version | Date | Author | Status |
|---------|------|--------|--------|
| 5.5 | 2026-02-20 | Codex | PARITY CLOSURE PASS IMPLEMENTED (CODE + BUILD VERIFIED) |

---

## **23. Incident Fix Log: TG-user web auth + `/start` crash (Codex, 2026-02-20)**

### **23.1 RCA (Root Cause Analysis)**

- Bot crash on `/start` was caused by DI context mismatch in router handlers:
  - `on_start_command` was a `@router.message(...)` handler but used `dishka.integrations.aiogram_dialog.inject`.
  - This led to missing injected argument at runtime: `referral_service`.
  - Evidence: `src/bot/routers/menu/handlers.py:44`, `src/bot/routers/menu/handlers.py:45`, `src/bot/routers/menu/handlers.py:51`.

- Web `400` on `POST /api/v1/auth/register` for some users was not a crash but expected business behavior:
  - If Telegram user already has attached web credentials, backend returns: `"Telegram ID already registered. Please login."`.
  - Evidence: `src/services/auth.py:76`, `src/services/auth.py:77`.

### **23.2 Implemented Fixes**

- Applied explicit aiogram DI for router handlers (without enabling global `auto_inject=True`):
  - `src/bot/routers/menu/handlers.py`:
    - split injectors into `aiogram_inject` for `@router.message` and `dialog_inject` for dialog callbacks.
    - `on_start_command` decorators ordered as `@router.message(...)` then `@aiogram_inject`.
  - `src/bot/routers/extra/commands.py`:
    - `on_paysupport_command`, `on_help_command` moved to `aiogram_inject` with correct decorator order.
  - `src/bot/routers/extra/test.py`:
    - `on_test_command` moved to `aiogram_inject`; dialog callback `show_dev_popup` kept on dialog injector.
  - `src/bot/routers/extra/member.py`:
    - added `@aiogram_inject` for `my_chat_member` handlers.
  - `src/bot/routers/extra/payment.py`:
    - added `@aiogram_inject` for `on_successful_payment`.

- Improved web registration UX for TG users:
  - `web-app/src/pages/auth/RegisterPage.tsx` now maps backend `already registered / please login` details to explicit RU guidance:
    - `"Этот Telegram ID уже привязан к web-аккаунту. Войдите через страницу входа."`
  - Added direct CTA link to `/auth/login` in this error state.

- Added operational explanation to docs:
  - `docs/README.md`: section **"Как TG-пользователь входит в Web"**.

### **23.3 Verification**

- Static compile for DI-changed bot files:
  - `python -m py_compile src/bot/routers/menu/handlers.py src/bot/routers/extra/commands.py src/bot/routers/extra/test.py src/bot/routers/extra/member.py src/bot/routers/extra/payment.py` -> PASS.

- Decorator order and injector checks:
  - No remaining wrong-order pattern `@aiogram_inject` above `@router.*`.
  - Router handlers now consistently follow `@router...` then `@aiogram_inject`.

### **23.4 Notes**

- Public API contract was not changed in this incident pass.
- `setup_aiogram_dishka(..., auto_inject=True)` remains intentionally disabled (explicit strategy retained).
