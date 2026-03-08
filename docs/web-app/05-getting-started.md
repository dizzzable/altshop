> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - Getting Started Guide

## Quick Reference

This document provides a quick start guide for implementing the AltShop web application.

---

## Project Overview

**Goal:** Build a user-facing web application that mirrors all user-facing Telegram bot features.

**Scope:** USERS ONLY - Admin/Dev features remain in Telegram bot.

**Tech Stack:**
- Frontend: React 19.2.4 + TypeScript + Shadcn UI + Tailwind CSS 4
- Backend: FastAPI (existing) + new user endpoints
- Auth: Telegram OAuth + JWT
- Database: PostgreSQL (existing) + web_sessions table

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Overall implementation strategy |
| [01-ui-ux-design.md](01-ui-ux-design.md) | UI/UX design specifications |
| [02-component-design.md](02-component-design.md) | React component specifications |
| [03-api-design.md](03-api-design.md) | API endpoint specifications |
| [04-database-schema.md](04-database-schema.md) | Database schema extensions |
| [05-getting-started.md](05-getting-started.md) | This document |

---

## Phase 1: Setup (Week 1-2)

### Step 1: Initialize Frontend Project

```bash
# Create project directory
mkdir altshop-web
cd altshop-web

# Initialize with Vite + React + TypeScript
npm create vite@latest . -- --template react-ts

# Install dependencies
npm install

# Install Tailwind CSS 4
npm install tailwindcss @tailwindcss/vite

# Install Shadcn UI
npx shadcn@latest init

# Install core components
npx shadcn@latest add button card input label dialog dropdown-menu
npx shadcn@latest add avatar badge tabs table form toast sonner
npx shadcn@latest add select switch slider separator progress skeleton
npx shadcn@latest add sheet navigation-menu alert-dialog

# Install additional dependencies
npm install react-router-dom @tanstack/react-query zustand
npm install react-hook-form @hookform/resolvers zod
npm install @telegram-apps/sdk jwt-decode
npm install lucide-react class-variance-authority clsx tailwind-merge

# Install dev dependencies
npm install -D @types/node
```

### Step 2: Configure Project

**vite.config.ts:**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
```

**tsconfig.json:**
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**src/index.css:**
```css
@import "tailwindcss";

@plugin "tailwindcss-animate";

@custom-variant dark (&:is(.dark *));

:root {
  /* Add theme variables from UI/UX design doc */
}

.dark {
  /* Add dark theme variables */
}
```

### Step 3: Create Project Structure

```bash
# Create directory structure
mkdir -p src/{components,hooks,lib,pages,stores,types,styles}
mkdir -p src/components/{ui,layout,features}
mkdir -p src/components/features/{subscription,devices,referrals,partner,promocodes}
mkdir -p src/pages/{auth,dashboard}
mkdir -p src/styles
```

### Step 4: Set Up Backend Extensions

```bash
# In main altshop project
cd altshop

# Create new endpoint file
touch src/api/endpoints/web_user.py

# Create migration
alembic -c src/infrastructure/database/alembic.ini revision --autogenerate -m "add web sessions"

# Apply migration
alembic -c src/infrastructure/database/alembic.ini upgrade head
```

---

## Phase 2: Authentication (Week 2-3)

### Step 1: Implement Backend Auth

**File:** `src/api/endpoints/web_auth.py`

```python
# Copy auth endpoints from IMPLEMENTATION_PLAN.md
# - POST /api/v1/auth/telegram
# - POST /api/v1/auth/refresh
# - POST /api/v1/auth/logout
```

### Step 2: Create Frontend Auth Components

**File:** `src/components/auth/AuthProvider.tsx`
**File:** `src/components/auth/ProtectedRoute.tsx`
**File:** `src/components/auth/TelegramLogin.tsx`

### Step 3: Set Up Routing

**File:** `src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './components/auth/AuthProvider';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute } from './components/auth/PublicRoute';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { LoginPage } from './pages/auth/Login';
import { DashboardPage } from './pages/dashboard/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/auth/login" element={
            <PublicRoute>
              <LoginPage />
            </PublicRoute>
          } />
          
          {/* Protected routes */}
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }>
            <Route index element={<DashboardPage />} />
            {/* Add more dashboard routes */}
          </Route>
          
          {/* Redirects */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

---

## Phase 3: Core Features (Week 3-6)

### Week 3: Dashboard & Subscriptions

1. **Dashboard Page** - User overview
2. **Subscription List** - View all subscriptions
3. **Subscription Card** - Individual subscription display
4. **Purchase Flow** - Buy new subscription

### Week 4: Devices & Referrals

1. **Devices Page** - Manage connected devices
2. **Referrals Page** - Referral program
3. **Referral Link Component** - Share link
4. **QR Code Generation** - QR code for referrals

### Week 5: Partner & Promocodes

1. **Partner Page** - Partner dashboard
2. **Partner Earnings** - View earnings
3. **Withdraw Form** - Request withdrawal
4. **Promocodes Page** - Activate promocodes

### Week 6: Settings & Polish

1. **Settings Page** - User settings
2. **Theme Toggle** - Light/dark mode
3. **Language Switcher** - Multi-language support
4. **Bug Fixes** - Fix issues from testing

---

## Phase 4: Testing & Deployment (Week 7-8)

### Testing Checklist

- [ ] Auth flow (login, logout, refresh)
- [ ] Subscription list and details
- [ ] Purchase flow (all gateways)
- [ ] Renewal flow
- [ ] Device management
- [ ] Referral link sharing
- [ ] Partner withdrawals
- [ ] Promocode activation
- [ ] Settings updates
- [ ] Mobile responsiveness
- [ ] Accessibility (keyboard navigation, screen readers)
- [ ] Performance (Lighthouse score > 90)

### Deployment Steps

1. **Build frontend:**
   ```bash
   npm run build
   ```

2. **Configure nginx:**
   ```nginx
   server {
       listen 443 ssl;
       server_name bot.domain.com;
       
       location / {
           root /opt/altshop-web/dist;
           try_files $uri $uri/ /index.html;
       }
       
       location /api {
           proxy_pass http://localhost:5000;
           # ... proxy settings
       }
   }
   ```

3. **Set up SSL:**
   ```bash
   certbot --nginx -d bot.domain.com
   ```

4. **Configure environment:**
   ```bash
   # Add to .env
   WEB_APP_URL=https://bot.domain.com
   CORS_ORIGINS=https://bot.domain.com
   ```

5. **Start services:**
   ```bash
   docker compose up -d
   ```

---

## Common Tasks

### Add New Component

```bash
# Create component file
touch src/components/features/my-feature/MyComponent.tsx

# Add to component index
echo "export { MyComponent } from './features/my-feature/MyComponent';" >> src/components/index.ts
```

### Add New Page

```bash
# Create page file
touch src/pages/dashboard/MyPage.tsx

# Add route in App.tsx
<Route path="my-page" element={<MyPage />} />
```

### Add New API Endpoint

```python
# In src/api/endpoints/web_user.py
@router.get("/my-endpoint")
async def my_endpoint(user: UserDto = Depends()):
    return {"message": "Hello"}
```

### Run Type Check

```bash
npm run type-check
```

### Run Linter

```bash
npm run lint
```

### Build for Production

```bash
npm run build
```

---

## Troubleshooting

### Issue: Telegram OAuth not working

**Solution:**
1. Verify bot domain is set via @Botfather
2. Check BOT_SECRET_TOKEN matches
3. Verify hash calculation algorithm
4. Check auth_date is within 24 hours

### Issue: CORS errors

**Solution:**
1. Add frontend URL to CORS_ORIGINS in .env
2. Ensure credentials: 'include' in API calls
3. Check nginx proxy configuration

### Issue: Session not persisting

**Solution:**
1. Verify httpOnly cookies are being set
2. Check cookie domain/path settings
3. Ensure HTTPS in production
4. Verify token expiration times

### Issue: Mobile layout broken

**Solution:**
1. Check responsive breakpoints
2. Test on actual devices, not just dev tools
3. Verify flexbox/grid configurations
4. Check for fixed widths that should be relative

---

## Resources

### Documentation
- [React](https://react.dev/learn)
- [Shadcn UI](https://ui.shadcn.com/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [React Router](https://reactrouter.com/)
- [TanStack Query](https://tanstack.com/query/latest)
- [Telegram Web Apps](https://core.telegram.org/bots/webapps)

### Tools
- [v0.dev](https://v0.dev/) - AI-powered UI generation
- [shadcn/ui CLI](https://ui.shadcn.com/docs/cli) - Component management
- [React DevTools](https://react.dev/learn/react-developer-tools) - Debugging

### Community
- [React Discord](https://discord.gg/react)
- [Shadcn Discord](https://discord.gg/shadcn)
- [r/reactjs](https://reddit.com/r/reactjs)

---

## Success Criteria

### Functional
- [ ] All user-facing bot features available on web
- [ ] Telegram OAuth working
- [ ] All payment gateways functional
- [ ] Mobile responsive
- [ ] Fast page loads (< 3s)

### Technical
- [ ] TypeScript strict mode enabled
- [ ] No console errors
- [ ] Lighthouse score > 90
- [ ] Test coverage > 80%
- [ ] Accessibility AA compliant

### Business
- [ ] Users can purchase subscriptions
- [ ] Users can manage devices
- [ ] Users can view referrals
- [ ] Users can activate promocodes
- [ ] Zero data loss
- [ ] Zero security incidents

---

## Contact

For questions or issues, refer to the main project documentation or contact the development team.

**Good luck with the implementation! 🚀**
