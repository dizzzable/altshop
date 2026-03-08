> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../docs/README.md)

# AltShop Web Application

A modern, responsive web application for managing VPN subscriptions, built with React 19, TypeScript, and Tailwind CSS.

## 🌟 Features

- **Telegram OAuth** - Secure authentication via Telegram
- **Subscription Management** - View, purchase, and renew VPN subscriptions
- **Device Management** - Manage connected devices and generate connection links
- **Referral Program** - Invite friends and earn rewards
- **Partner Program** - 3-level partner commission system
- **Promocodes** - Activate promocodes for rewards
- **Settings** - Manage account settings and preferences
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Dark Mode** - Built-in dark theme support

## 🛠️ Tech Stack

- **Frontend Framework:** React 19.2.4
- **Language:** TypeScript 5.7
- **Build Tool:** Vite 6
- **Styling:** Tailwind CSS 4
- **UI Components:** Shadcn UI + Radix UI
- **State Management:** Zustand, TanStack Query
- **Routing:** React Router 7
- **Forms:** React Hook Form + Zod
- **HTTP Client:** Axios
- **Notifications:** Sonner

## 📋 Prerequisites

- Node.js 18+ 
- npm or yarn
- AltShop backend API running

## 🚀 Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Create a `.env` file in the root directory:

```bash
# Telegram Bot Username (for login widget)
VITE_TELEGRAM_BOT_USERNAME=altshop_bot

# API Base URL (optional, defaults to /api/v1)
# VITE_API_BASE_URL=https://bot.domain.com/api/v1

# Enable Telegram mobile UI v2 (mobile landing, paged bottom nav, compact subscriptions)
# VITE_MOBILE_TELEGRAM_UI_V2=true
```

### 3. Start Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### 4. Build for Production

```bash
npm run build
```

### 5. Preview Production Build

```bash
npm run preview
```

## 📁 Project Structure

```
web-app/
├── src/
│   ├── components/
│   │   ├── ui/              # Shadcn UI components
│   │   ├── auth/            # Authentication components
│   │   └── layout/          # Layout components
│   ├── pages/
│   │   ├── auth/            # Auth pages
│   │   └── dashboard/       # Dashboard pages
│   ├── lib/
│   │   ├── api.ts           # API client
│   │   └── utils.ts         # Utility functions
│   ├── stores/
│   │   └── auth-store.ts    # Auth state management
│   ├── types/
│   │   └── index.ts         # TypeScript types
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.ts
```

## 🔌 API Integration

The application connects to the AltShop backend API. All API calls are made through the centralized API client in `src/lib/api.ts`.

### Available Endpoints

- `POST /api/v1/auth/telegram` - Telegram OAuth
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user
- `GET /api/v1/subscription/list` - List subscriptions
- `POST /api/v1/subscription/purchase` - Purchase subscription
- `GET /api/v1/plans` - List plans
- `POST /api/v1/promocode/activate` - Activate promocode
- `GET /api/v1/referral/info` - Get referral info
- `GET /api/v1/partner/info` - Get partner info
- And more...

### Proxy Configuration

During development, API requests are proxied to the backend:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:5000',
      changeOrigin: true,
    },
  },
}
```

## 🎨 Customization

### Theme Colors

Edit `src/index.css` to customize theme colors:

```css
:root {
  --color-primary: #3B82F6;
  --color-secondary: #10B981;
  /* ... */
}
```

### Adding New Pages

1. Create page component in `src/pages/dashboard/`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/layout/Sidebar.tsx`

### Adding New Components

1. Create component in `src/components/`
2. Export from `src/components/index.ts` (if creating shared component)

## 🧪 Testing

### Run Type Check

```bash
npm run type-check
```

### Run Linter

```bash
npm run lint
```

## 📦 Deployment

### Build Output

The build command creates optimized production files in the `dist/` directory.

### Deploy to Production

1. Build the application: `npm run build`
2. Copy `dist/` contents to your web server
3. Configure web server to serve `index.html` for all routes (SPA)
4. Set up environment variables

### Nginx Configuration Example

```nginx
server {
    listen 443 ssl;
    server_name bot.domain.com;
    
    root /var/www/altshop-web/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔐 Security

- JWT tokens stored in localStorage
- Automatic token refresh
- Protected routes require authentication
- HTTPS required in production
- CORS configured for API access

## 📱 Responsive Breakpoints

- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📄 License

MIT License - See main project repository for details.

## 🆘 Support

For issues or questions:
1. Check documentation
2. Review existing issues
3. Contact support team

## 📊 Project Stats

- **Components:** 27+
- **Pages:** 9
- **Lines of Code:** ~4,500+
- **Development Time:** 8 days

---

Built with ❤️ using React, TypeScript, and Tailwind CSS
