<div align="center" markdown>

<p align="center">
    <u><b>ENGLISH</b></u> •
    <a href="README.ru_RU.md"><b>РУССКИЙ</b></a>
</p>

# 🛒 ALTSHOPAI

**Telegram bot for selling VPN subscriptions, integrated with Remnawave.**

> ⚠️ **DISCLAIMER**: This code was written with the assistance of AI and is based on the original project [snoups/remnashop](https://github.com/snoups/remnashop). The new developer assumes NO responsibility for any malfunctions, errors, or issues that may arise from using this software. Use at your own risk. This project is provided completely FREE of charge.

</div>

---

## ✨ Implemented Features

### 📦 Plans
- ✅ Flexible plan creation with unique architecture
- ✅ Support for any limits — traffic, devices, combined, or unlimited
- ✅ Plan availability control for specific user types or individual users
- ✅ Internal and external squad linking to specific plans
- ✅ Support for any subscription duration
- ✅ Free duration options available
- ✅ Multi-currency pricing for each duration (USD, RUB, XTR, USDT, TON, BTC, ETH, LTC)
- ✅ Customizable plan display order
- ✅ Built-in plan configurator in bot interface
- ✅ **Multiple subscriptions purchase** — users can buy any number of subscriptions, not limited to one
- ✅ **Subscription count per plan** — configurable number of subscriptions per plan purchase
- ✅ Traffic limit strategies: no reset, daily, weekly, monthly

### 🎟️ Promocodes
- ✅ Multiple reward types: extra days, traffic, devices, subscription activation, personal discount, next purchase discount
- ✅ Configurable lifetime: by time or number of activations
- ✅ Convenient promocode configurator
- ✅ **Promocode availability settings**: all users, new users, existing users, invited users, specific users
- ✅ **Apply promocode to specific subscription** — choose which subscription to extend

### 📢 Broadcasts
- ✅ View all previously sent messages with content preview
- ✅ Send by user category: all users, by plan, with/without subscription, expired, or trial
- ✅ Support for photos, videos, GIFs, and stickers
- ✅ HTML tags support for message formatting
- ✅ Preview messages before sending
- ✅ Stop active broadcast option
- ✅ Delete sent messages option

### 🔔 Notifications
- ✅ Configurable notification system in bot interface
- ✅ User notifications: subscription expiring (3, 2, 1 days), expired, expired 1 day ago, traffic exhausted
- ✅ System notifications: bot lifecycle, updates, new user registration, subscription activation, promocode activation, trial, node status, first connection, device add/remove events
- ✅ **Referral notifications**: new referral attached, referral reward received

### 🧪 Trial
- ✅ Configurable trial setup through plan configurator
- ✅ Support for any limits
- ✅ Multiple trial plans support
- ✅ Separate internal and external squad assignments
- ✅ Availability settings for referral or ad link users

### 👥 Referral System
- ✅ Detailed referral statistics
- ✅ Referral system configurator
- ✅ Reward customization: points (money) or extra days
- ✅ **Two-level referral support** — earn from referrals of your referrals
- ✅ **Reward strategies**: fixed amount or percentage of payment/subscription duration
- ✅ **Accrual strategies**: on first payment only or on each payment
- ✅ **Plan filter for referral rewards** — only specific plans trigger rewards
- ✅ **QR code generation** for referral links with custom logo
- ✅ **Points exchange system**: exchange points for subscription days, gift subscriptions, discounts, or traffic

### 💳 Payment System
- ✅ Multiple payment gateways: Telegram Stars, YooKassa, CryptoPay, Heleket, Pal24, Platega, Wata, Cryptomus, YooMoney, RoboKassa
- ✅ Payment gateway configurator
- ✅ Default currency setup
- ✅ Test payment capability
- ✅ Customizable payment method display order
- ✅ **Purchase types**: new subscription, renewal, additional subscription

### 📱 Device Management
- ✅ User device management (with active subscriptions and within limits)
- ✅ Configurable cooldown for device reset actions
- ✅ **Device type tracking**: Android, iPhone, Windows, Mac

### 🏷️ Discount System
- ✅ Two discount types: personal and next purchase
- ✅ Largest discount applied (no stacking)
- ✅ Discount display on purchase buttons

### 🔐 Access Mode
- ✅ Five access modes: full restriction, open, invite-only, purchase restricted, register restricted
- ✅ Automatic notifications for restricted mode purchase attempts
- ✅ Conditional access: rule acceptance and channel subscription
- ✅ **Rules acceptance tracking** per user

### 📈 Ad Links
- ✅ Traffic source tracking links
- ✅ Built-in link configurator
- ✅ Detailed analytics for each link

### 📊 Statistics
- ✅ Detailed analytics: users, transactions, subscriptions, plans, promocodes, referrals

### 👤 User Editor
- ✅ Complete user information: profile, stats, subscription, transactions
- ✅ Personal discount editing
- ✅ Role management: developer, admin, user
- ✅ User blocking
- ✅ Plan access granting
- ✅ Full subscription editor: limits, traffic reset, devices, squads, expiration, status toggle, deletion, connection link
- ✅ Banned users view
- ✅ Search by name, username, and ID
- ✅ Recent registrations and active users view
- ✅ Quick access via forwarded messages, notifications, or menu search
- ✅ **Points balance management**
- ✅ **Bot block status tracking** — know when user blocked the bot

### 🔄 User Synchronization
- ✅ Automatic synchronization with panel
- ✅ Edit user data from bot or panel

### 🔍 User Audit
- ✅ Full user activity history view

### 🌐 Internationalization
- ✅ Unique banners for each locale
- ✅ Interface translations support (27+ languages)
- ✅ Automatic language detection on first launch and changes

### 🧭 Migration
- ✅ Seamless migration from other bots

### 🪄 MiniApp Support
- ✅ MiniApp support (maposia)

### 🔧 Technical Features
- ✅ Redis caching for performance
- ✅ TaskIQ for background tasks and scheduled jobs
- ✅ Automatic expired subscription cleanup
- ✅ Webhook support for Remnawave panel events
- ✅ Message effects support (fire, like, dislike, love, confetti, poop)

---

## ⚠️ Important Notice

This project is:
- 🤖 **Written with AI assistance**
- 📦 **Based on [snoups/remnashop](https://github.com/snoups/remnashop)**
- 🆓 **Completely FREE**
- ⚡ **Provided AS-IS without any warranty**

The developer assumes **NO responsibility** for:
- Any malfunctions or errors
- Data loss or corruption
- Security vulnerabilities
- Any damages arising from the use of this software

---

## 📄 License

This project is distributed under the same license as the original [remnashop](https://github.com/snoups/remnashop) project.

---

## 🙏 Credits

- Original project: [snoups/remnashop](https://github.com/snoups/remnashop)
- AI-assisted development
