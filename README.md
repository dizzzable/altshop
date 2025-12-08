<div align="center" markdown>

<p align="center">
    <u><b>ENGLISH</b></u> •
    <a href="README.ru_RU.md"><b>РУССКИЙ</b></a>
</p>

# 🛒 AltShop

**Telegram bot for selling VPN subscriptions, integrated with Remnawave.**

**GitHub:** https://github.com/dizzzable/altshop

> ⚠️ **DISCLAIMER**: This code was written with the help of AI and is based on the original project [snoups/remnashop](https://github.com/snoups/remnashop). The new developer is NOT responsible for any malfunctions, errors, or problems that may arise from using this software. Use at your own risk. This project is provided completely FREE.

</div>

---

## ✨ Implemented Features

### 📦 Plans
- ✅ Flexible plan creation with unique architecture
- ✅ Support for any limits — traffic, devices, combined, or unlimited
- ✅ Plan availability management for specific user types or individual users
- ✅ Binding internal and external squads to specific plans
- ✅ Support for any subscription duration
- ✅ Free duration options available
- ✅ Multi-currency prices for each duration (USD, RUB, XTR, USDT, TON, BTC, ETH, LTC)
- ✅ Customizable plan display order
- ✅ Built-in plan configurator in bot interface
- ✅ **Multiple subscription purchases** — users can buy any number of subscriptions, not limited to one
- ✅ **Subscriptions per plan** — configurable number of subscriptions when purchasing a plan
- ✅ Traffic reset strategies: no reset, daily, weekly, monthly

### 🎟️ Promo Codes
- ✅ Various reward types: extra days, traffic, devices, subscription activation, personal discount, discount on next purchase
- ✅ Configurable lifetime: by time or number of activations
- ✅ Convenient promo code configurator
- ✅ **Promo code availability settings**: all users, new, existing, invited, specific users
- ✅ **Apply promo code to specific subscription** — choose subscription for extension

### 📢 Broadcasts
- ✅ View all sent messages with content preview
- ✅ Send by user categories: all, by plan, with/without subscription, expired, trial
- ✅ Support for photos, videos, GIFs, and stickers
- ✅ HTML tag support for message formatting
- ✅ Message preview before sending
- ✅ Ability to stop active broadcast
- ✅ Ability to delete sent messages

### 🔔 Notifications
- ✅ Configurable notification system in bot interface
- ✅ User notifications: subscription expiration (3, 2, 1 day before), subscription expired, expired 1 day ago, traffic exhausted
- ✅ System notifications: bot lifecycle, updates, new user registration, subscription activation, promo code activation, trial period, node status, first connection, device add/remove events
- ✅ **Referral notifications**: new referral joined, referral reward received

### 🧪 Trial Period
- ✅ Trial period setup via plan configurator
- ✅ Support for any limits
- ✅ Support for multiple trial plans
- ✅ Separate internal and external squad assignments
- ✅ Availability settings for users from referral or advertising links

### 👥 Referral System
- ✅ Detailed referral statistics
- ✅ Referral system configurator
- ✅ Reward configuration: points (money) or extra days
- ✅ **Two-level referral system** — earn from your referrals' referrals
- ✅ **Reward strategies**: fixed amount or percentage of payment/subscription duration
- ✅ **Accrual strategies**: only on first payment or on every payment
- ✅ **Plan filter for referral rewards** — only specific plans trigger rewards
- ✅ **QR code generation** for referral links with custom logo
- ✅ **Points exchange system**: exchange points for subscription days, gift subscriptions, discounts, or traffic

### 💳 Payment System
- ✅ Multiple payment gateways: Telegram Stars, YooKassa, CryptoPay, Heleket, Pal24, Platega, Wata, Cryptomus, YooMoney, RoboKassa
- ✅ Payment gateway configurator
- ✅ Default currency configuration
- ✅ Test payment capability
- ✅ Customizable payment method display order
- ✅ **Purchase types**: new subscription, renewal, additional subscription

### 📱 Device Management
- ✅ User device management (with active subscription and within limits)
- ✅ Configurable interval for device reset
- ✅ **Device type tracking**: Android, iPhone, Windows, Mac

### 🏷️ Discount System
- ✅ Two discount types: personal and next purchase
- ✅ Highest discount applied (no stacking)
- ✅ Discount display on purchase buttons

### 🔐 Access Mode
- ✅ Five access modes: full restriction, open, by invitation, purchase restriction, registration restriction
- ✅ Automatic notifications on purchase attempts in restricted mode
- ✅ Conditional access: rules acceptance and channel subscription
- ✅ **Rules acceptance tracking** for each user

### 📈 Advertising Links
- ✅ Links for tracking traffic sources
- ✅ Built-in link configurator
- ✅ Detailed analytics for each link

### 📊 Statistics
- ✅ Detailed analytics: users, transactions, subscriptions, plans, promo codes, referrals

### 👤 User Editor
- ✅ Complete user information: profile, statistics, subscription, transactions
- ✅ Personal discount editing
- ✅ Role management: developer, administrator, user
- ✅ User blocking
- ✅ Plan access granting
- ✅ Full subscription editor: limits, traffic reset, devices, squads, expiration, status toggle, deletion, connection link
- ✅ View blocked users
- ✅ Search by name, username, and ID
- ✅ View recent registrations and active users
- ✅ Quick access via forwarded messages, notifications, or menu search
- ✅ **Points balance management**
- ✅ **Bot block tracking** — know when a user blocked the bot

### 🔄 User Synchronization
- ✅ Automatic synchronization with panel
- ✅ Edit user data from bot or panel

### 🔍 User Audit
- ✅ View complete user activity history

### 🌐 Internationalization
- ✅ Unique banners for each locale
- ✅ Interface translation support (27+ languages)
- ✅ Automatic language detection on first launch and changes

### 🧭 Migration
- ✅ Seamless migration from other bots

### 🪄 MiniApp Support
- ✅ MiniApp support (maposia)

### 🔧 Technical Features
- ✅ Redis caching for performance
- ✅ TaskIQ for background tasks and scheduled jobs
- ✅ Automatic cleanup of expired subscriptions
- ✅ Webhook support for Remnawave panel events
- ✅ Message effects support (fire, like, dislike, heart, confetti, poop)

---

## 📋 Requirements

- Docker and Docker Compose
- Domain with SSL certificate (for webhook)
- Remnawave Panel (installed and configured)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/dizzzable/altshop.git
cd altshop/ALTSHOP
```

### 2. Configure Environment Variables

Copy the example file and edit it:

```bash
cp .env.example .env
nano .env
```

#### Main Parameters to Configure:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `APP_DOMAIN` | Bot domain (without http/https) | `bot.example.com` |
| `APP_CRYPT_KEY` | Encryption key (generate unique) | `your-secret-key-32chars` |
| `BOT_TOKEN` | Telegram bot token | `123456:ABC-DEF...` |
| `BOT_SECRET_TOKEN` | Secret token for webhook | `random-secret-string` |
| `BOT_DEV_ID` | Your Telegram ID | `123456789` |
| `BOT_SUPPORT_USERNAME` | Support username (without @) | `support_user` |
| `REMNAWAVE_HOST` | Remnawave Panel host | `remnawave` or `panel.example.com` |
| `REMNAWAVE_TOKEN` | Remnawave API token | `your-api-token` |
| `REMNAWAVE_WEBHOOK_SECRET` | Remnawave webhook secret | `webhook-secret` |
| `DATABASE_PASSWORD` | PostgreSQL password | `strong-password` |
| `REDIS_PASSWORD` | Redis password | `strong-password` |

### 3. Configure SSL Certificates

Place SSL certificates in the `nginx/` folder:

```bash
# Create nginx folder if it doesn't exist
mkdir -p nginx

# Copy your certificates
cp /path/to/fullchain.pem nginx/remnabot_fullchain.pem
cp /path/to/privkey.key nginx/remnabot_privkey.key
```

### 4. Configure Nginx

Edit `nginx/nginx.conf` and replace `bot.dmain.com` with your domain:

```bash
nano nginx/nginx.conf
```

Replace all occurrences of `bot.dmain.com` with your domain.

### 5. Configure Remnawave Panel

In the Remnawave Panel `.env` file, add:

```env
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://bot.example.com/api/v1/remnawave
WEBHOOK_SECRET_HEADER=your-webhook-secret
```

### 6. Start the Bot

```bash
docker compose up -d
```

Check logs:

```bash
docker compose logs -f remnashop
```

---

## 📁 Project Structure

```
ALTSHOP/
├── .env.example          # Configuration example
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Production Dockerfile
├── Dockerfile.local      # Development Dockerfile
├── docker-entrypoint.sh  # Startup script
├── assets/               # Resources (banners, translations)
│   ├── banners/          # Bot banners
│   └── translations/     # Localization files
├── nginx/                # Nginx configuration
│   ├── nginx.conf        # Nginx config
│   └── docker-compose.yml # Separate compose for Nginx
└── src/                  # Bot source code
```

---

## 🔧 Additional Configuration

### Localization

The bot supports multiple languages. Configure in `.env`:

```env
APP_LOCALES=ru,en
APP_DEFAULT_LOCALE=ru
```

Translation files are located in `assets/translations/`.

### Banners

Add banners to `assets/banners/`:
- `default.jpg` - default banner
- `ru/` - banners for Russian language
- `en/` - banners for English language

Enable banner usage:

```env
BOT_USE_BANNERS=true
```

### Mini App

To use Mini App (subscription page):

```env
# Open subscription page in WebApp
BOT_MINI_APP=true

# Or specify custom URL
BOT_MINI_APP=https://your-subscription-page.com/
```

---

## 🔄 Update

```bash
cd altshop/ALTSHOP
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## 🛠 Useful Commands

```bash
# View logs
docker compose logs -f remnashop

# Restart bot
docker compose restart remnashop

# Stop all services
docker compose down

# View container status
docker compose ps

# Enter bot container
docker compose exec remnashop sh

# Reset assets (banners, translations)
RESET_ASSETS=true docker compose up -d
```

---

## 🐛 Troubleshooting

### Bot Not Responding

1. Check logs: `docker compose logs -f remnashop`
2. Make sure webhook is configured correctly
3. Check SSL certificates

### Database Connection Error

1. Check that DB container is running: `docker compose ps`
2. Check password in `.env`
3. Try recreating containers: `docker compose down -v && docker compose up -d`

### Remnawave Connection Error

1. Check `REMNAWAVE_HOST` and `REMNAWAVE_PORT`
2. Make sure Remnawave Panel is accessible
3. Check `REMNAWAVE_TOKEN`

---

## ⚠️ Important Notice

This project:
- 🤖 **Written with AI assistance**
- 📦 **Based on [snoups/remnashop](https://github.com/snoups/remnashop)**
- 🆓 **Completely FREE**
- ⚡ **Provided AS IS without any warranties**

The developer is **NOT responsible** for:
- Any malfunctions or errors
- Data loss or corruption
- Security vulnerabilities
- Any damage resulting from using this software

---

## 📞 Support

- **GitHub Issues:** https://github.com/dizzzable/altshop/issues

---

## 📄 License

This project is distributed under the same license as the original [remnashop](https://github.com/snoups/remnashop) project.

---

## 🙏 Acknowledgments

- Original project: [snoups/remnashop](https://github.com/snoups/remnashop)
- Development with AI assistance
