> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application Implementation Plan
## User-Facing Web Interface (Admin/Dev Features Remain in Telegram)

---

## Executive Summary

This document outlines the implementation plan for building an **external web application for END USERS ONLY**. The web app will mirror all **user-facing** Telegram bot functionality, allowing regular users to manage their VPN subscriptions through a modern web interface.

### ⚠️ Critical Scope Definition

| Feature Category | Web App | Telegram Bot |
|-----------------|---------|--------------|
| **User Features** | ✅ YES | ✅ Also available |
| - View subscriptions | ✅ | ✅ |
| - Purchase subscriptions | ✅ | ✅ |
| - Renew subscriptions | ✅ | ✅ |
| - Manage devices | ✅ | ✅ |
| - Referral program | ✅ | ✅ |
| - Partner program (user side) | ✅ | ✅ |
| - Activate promocodes | ✅ | ✅ |
| - Account settings | ✅ | ✅ |
| **Admin/Dev Features** | ❌ NO | ✅ ONLY |
| - User management | ❌ | ✅ |
| - Broadcast messaging | ❌ | ✅ |
| - Plan configuration | ❌ | ✅ |
| - Gateway configuration | ❌ | ✅ |
| - Statistics & analytics | ❌ | ✅ |
| - Backup/restore | ❌ | ✅ |
| - System settings | ❌ | ✅ |
| - Import users | ❌ | ✅ |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USERS                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Telegram App   │  │  Mobile Browser │  │ Desktop Browser │ │
│  │   (Mini App)    │  │                 │  │                 │ │
│  │   USER ONLY     │  │   USER ONLY     │  │   USER ONLY     │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
└───────────┼────────────────────┼────────────────────┼───────────┘
            │                    │                    │
            │   Telegram OAuth   │   Telegram OAuth   │
            │   JWT Token        │   JWT Token        │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NGINX (Reverse Proxy)                         │
│  SSL Termination | Rate Limiting | CORS | Compression           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
    ┌───────▼───────┐ ┌─────▼──────┐ ┌─────▼──────┐
    │   Frontend    │ │  Backend   │ │   Static   │
    │   (React SPA) │ │  (FastAPI) │ │   Files    │
    │   USER UI     │ │  USER API  │ │  (assets)  │
    └───────────────┘ └─────┬──────┘ └────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
    ┌───────▼───────┐ ┌─────▼──────┐ ┌─────▼──────┐
    │  PostgreSQL   │ │   Redis    │ │  Telegram  │
    │  (existing)   │ │  (cache)   │ │  API       │
    └───────────────┘ └────────────┘ └────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN/DEV FEATURES                            │
│                     TELEGRAM ONLY                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Existing Bot (Unchanged)                    │   │
│  │  - Dashboard management                                  │   │
│  │  - User management                                       │   │
│  │  - Broadcasts                                            │   │
│  │  - Plans configuration                                   │   │
│  │  - Gateways configuration                                │   │
│  │  - Statistics                                            │   │
│  │  - Backups                                               │   │
│  │  - Settings                                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## User-Only Feature Set

### Pages to Implement

| Page | Route | Description | Priority |
|------|-------|-------------|----------|
| **Auth** | `/auth/login` | Telegram OAuth login | P0 |
| **Dashboard** | `/dashboard` | User overview, subscription status | P0 |
| **My Subscriptions** | `/dashboard/subscription` | List all subscriptions | P0 |
| **Purchase** | `/dashboard/subscription/purchase` | Buy new subscription | P0 |
| **Renew** | `/dashboard/subscription/{id}/renew` | Renew existing | P0 |
| **Details** | `/dashboard/subscription/{id}` | View subscription details | P1 |
| **Devices** | `/dashboard/devices` | Manage connected devices | P1 |
| **Referrals** | `/dashboard/referrals` | Referral program, invite links | P1 |
| **Partner** | `/dashboard/partner` | Partner dashboard (if enrolled) | P1 |
| **Earnings** | `/dashboard/partner/earnings` | Partner earnings history | P2 |
| **Withdraw** | `/dashboard/partner/withdraw` | Request withdrawal | P2 |
| **Promocodes** | `/dashboard/promocodes` | Activate promocodes | P1 |
| **Settings** | `/dashboard/settings` | Account settings, language | P2 |
| **Support** | `/dashboard/support` | Contact support | P3 |

### Features NOT in Web App (Telegram Admin Only)

| Feature | Reason |
|---------|--------|
| User management | Admin only |
| Broadcast messaging | Admin only |
| Plan configuration | Admin only |
| Gateway configuration | Admin only |
| Statistics & analytics | Admin only |
| Backup/restore | Admin only |
| System settings | Admin only |
| Import users | Admin only |
| Remnawave panel view | Admin only |
| Notification settings | Admin only |

---

## Technology Stack (2025-2026 Latest)

### Frontend (User-Facing)

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.2.4 | UI framework (security-focused release) |
| **TypeScript** | 5.7+ | Type safety |
| **Vite** | 6.x | Build tool + dev server |
| **Tailwind CSS** | 4.x | Utility-first CSS |
| **Shadcn UI** | Latest (2025) | Component library |
| **React Router** | 7.x | Client-side routing |
| **TanStack Query** | 5.x | Server state management |
| **Zustand** | 5.x | Client state management |
| **React Hook Form** | 4.x | Form handling |
| **Sonner** | Latest | Toast notifications |
| **@telegram-apps/sdk** | 2.x | Telegram Mini App integration |

### Backend (Extension of Existing)

| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | 0.120.2+ | REST API for web (existing + new endpoints) |
| **Pydantic** | 2.11+ | Data validation |
| **SQLAlchemy** | 2.0+ | ORM (existing) |
| **python-jose** | Latest | JWT tokens |
| **httpx** | 0.28+ | HTTP client (existing) |

### Authentication

| Technology | Purpose |
|------------|---------|
| **Telegram Login Widget** | OAuth 2.0 authentication for web |
| **Telegram WebApp SDK** | Mini App integration (in-Telegram browser) |
| **JWT** | Session tokens |
| **httpOnly Cookies** | Secure token storage |

---

## Phase 1: Foundation & User Authentication

### 1.1 Project Setup

#### Frontend Structure (User-Only)
```
altshop-web/
├── src/
│   ├── components/
│   │   ├── ui/              # Shadcn UI components
│   │   ├── layout/          # User layout components
│   │   ├── auth/            # Auth components (Telegram login)
│   │   └── features/        # User feature components
│   │       ├── subscription/
│   │       ├── devices/
│   │       ├── referrals/
│   │       └── partner/
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useTelegram.ts
│   │   └── useApi.ts
│   ├── lib/
│   │   ├── api.ts           # API client
│   │   ├── auth.ts          # Auth utilities
│   │   ├── telegram.ts      # Telegram SDK
│   │   └── utils.ts
│   ├── pages/
│   │   ├── auth/
│   │   │   └── Login.tsx    # Telegram login page
│   │   ├── dashboard/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── SubscriptionPage.tsx
│   │   │   ├── PurchasePage.tsx
│   │   │   ├── DevicesPage.tsx
│   │   │   ├── ReferralsPage.tsx
│   │   │   ├── PartnerPage.tsx
│   │   │   ├── PromocodesPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   └── NotFound.tsx
│   ├── stores/
│   │   ├── auth-store.ts    # User auth state
│   │   └── ui-store.ts
│   ├── types/
│   │   ├── api.ts
│   │   ├── telegram.ts
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

#### Package.json Dependencies
```json
{
  "name": "altshop-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "react-router-dom": "^7.0.0",
    "@tanstack/react-query": "^5.60.0",
    "zustand": "^5.0.0",
    "react-hook-form": "^4.50.0",
    "@hookform/resolvers": "^4.0.0",
    "zod": "^3.24.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^3.0.0",
    "sonner": "^2.0.0",
    "@telegram-apps/sdk": "^2.0.0",
    "jwt-decode": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "shadcn": "^latest"
  }
}
```

### 1.2 Shadcn UI Setup (User Components Only)

```bash
# Initialize Shadcn UI
npx shadcn@latest init

# Install USER-FACING components only
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add input
npx shadcn@latest add label
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add avatar
npx shadcn@latest add badge
npx shadcn@latest add tabs
npx shadcn@latest add table
npx shadcn@latest add form
npx shadcn@latest add toast
npx shadcn@latest add sonner
npx shadcn@latest add navigation-menu
npx shadcn@latest add progress
npx shadcn@latest add skeleton
npx shadcn@latest add alert-dialog
npx shadcn@latest add select
npx shadcn@latest add switch
npx shadcn@latest add slider
npx shadcn@latest add separator
```

### 1.3 User Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER AUTHENTICATION FLOW                  │
└─────────────────────────────────────────────────────────────┘

1. User visits web app
   │
   ▼
2. Redirect to /auth/login
   │
   ▼
3. User clicks "Login with Telegram"
   │
   ▼
4. Telegram OAuth popup
   │
   ▼
5. User authorizes
   │
   ▼
6. Telegram returns user data + hash
   │
   ▼
7. Frontend sends to backend /api/v1/auth/telegram
   │
   ▼
8. Backend verifies hash, creates/finds user
   │
   ▼
9. Backend returns JWT tokens (httpOnly cookies)
   │
   ▼
10. Frontend redirects to /dashboard
   │
   ▼
11. All API calls include JWT token automatically
```

---

## Phase 2: User Feature Implementation

### 2.1 User Dashboard Page

**File:** `src/pages/dashboard/Dashboard.tsx`

```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export function Dashboard() {
  const { data: user } = useQuery({ queryKey: ['user'], queryFn: () => api.get('/user/me') });
  const { data: subscriptions } = useQuery({ 
    queryKey: ['subscriptions'], 
    queryFn: () => api.get('/subscription/list') 
  });

  const activeSub = subscriptions?.find(s => s.status === 'ACTIVE');
  const hasExpired = subscriptions?.some(s => s.status === 'EXPIRED');

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Welcome, {user?.data.name}!</h1>
        <Button onClick={() => navigate('/dashboard/subscription/purchase')}>
          Purchase Subscription
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={activeSub ? 'default' : 'destructive'}>
              {activeSub ? 'Active' : 'No Subscription'}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Subscriptions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{subscriptions?.length || 0}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Referral Points</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{user?.data.points || 0}</p>
          </CardContent>
        </Card>
      </div>

      {hasExpired && (
        <Card className="border-red-500">
          <CardHeader>
            <CardTitle>Expired Subscription</CardTitle>
          </CardHeader>
          <CardContent>
            <p>You have an expired subscription. Renew now to continue using the service.</p>
            <Button className="mt-4" onClick={() => navigate('/dashboard/subscription/renew')}>
              Renew Now
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

### 2.2 User Subscription Management

**File:** `src/pages/dashboard/SubscriptionPage.tsx`

```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

export function SubscriptionPage() {
  const { data: subscriptions } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => api.get<Subscription[]>('/subscription/list'),
  });

  const getStatusBadge = (status: string) => {
    const variants = {
      ACTIVE: 'default',
      EXPIRED: 'destructive',
      LIMITED: 'warning',
      DISABLED: 'secondary',
    };
    return <Badge variant={variants[status]}>{status}</Badge>;
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">My Subscriptions</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/dashboard/promocodes')}>
            Activate Promocode
          </Button>
          <Button onClick={() => navigate('/dashboard/subscription/purchase')}>
            Purchase New
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {subscriptions?.map((sub) => (
          <Card key={sub.id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle>{sub.plan.name}</CardTitle>
                  <CardDescription>{sub.plan.type}</CardDescription>
                </div>
                {getStatusBadge(sub.status)}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground">Traffic</p>
                <Progress value={(sub.traffic_used / sub.traffic_limit) * 100} />
                <p className="text-xs text-muted-foreground mt-1">
                  {formatBytes(sub.traffic_used)} / {formatBytes(sub.traffic_limit)}
                </p>
              </div>
              
              <div>
                <p className="text-sm text-muted-foreground">Devices</p>
                <p>{sub.devices_count} / {sub.device_limit}</p>
              </div>
              
              <div>
                <p className="text-sm text-muted-foreground">Expires In</p>
                <p className="font-medium">{formatDays(sub.expire_at)}</p>
              </div>

              <div className="flex gap-2 pt-4">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(sub.url);
                    toast.success('Link copied!');
                  }}
                >
                  Copy Connection Link
                </Button>
                {sub.status === 'ACTIVE' && (
                  <Button 
                    size="sm" 
                    onClick={() => navigate(`/dashboard/subscription/${sub.id}/renew`)}
                  >
                    Renew
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

### 2.3 User Purchase Flow

**File:** `src/pages/dashboard/PurchasePage.tsx`

```tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';

export function PurchasePage() {
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [selectedGateway, setSelectedGateway] = useState<string | null>(null);

  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => api.get<Plan[]>('/plans'),
  });

  const handlePurchase = async () => {
    if (!selectedPlan || !selectedDuration || !selectedGateway) return;

    const response = await api.post('/subscription/purchase', {
      plan_id: selectedPlan,
      duration_days: selectedDuration,
      purchase_type: 'NEW',
      gateway_type: selectedGateway,
    });

    // Redirect to payment gateway
    window.location.href = response.data.payment_url;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Purchase Subscription</h1>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Plan Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Select Plan</CardTitle>
          </CardHeader>
          <CardContent>
            <RadioGroup value={selectedPlan?.toString()} onValueChange={(v) => setSelectedPlan(Number(v))}>
              {plans?.map((plan) => (
                <div key={plan.id} className="flex items-center space-x-2 border p-4 rounded-lg">
                  <RadioGroupItem value={plan.id.toString()} id={plan.id.toString()} />
                  <Label htmlFor={plan.id.toString()} className="flex-1">
                    <p className="font-medium">{plan.name}</p>
                    <p className="text-sm text-muted-foreground">{plan.description}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Traffic: {formatBytes(plan.traffic_limit)} | Devices: {plan.device_limit}
                    </p>
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </CardContent>
        </Card>

        {/* Duration Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Select Duration</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={selectedDuration?.toString()} onValueChange={(v) => setSelectedDuration(Number(v))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose duration" />
              </SelectTrigger>
              <SelectContent>
                {plans?.find(p => p.id === selectedPlan)?.durations.map((d) => (
                  <SelectItem key={d.days} value={d.days.toString()}>
                    {d.days} days - {formatPrice(d.price)} {d.currency}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Payment Method */}
        <Card>
          <CardHeader>
            <CardTitle>Payment Method</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={selectedGateway} onValueChange={setSelectedGateway}>
              <SelectTrigger>
                <SelectValue placeholder="Choose payment method" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="telegram_stars">Telegram Stars</SelectItem>
                <SelectItem value="yookassa">YooKassa</SelectItem>
                <SelectItem value="cryptopay">CryptoPay</SelectItem>
                <SelectItem value="heleket">Heleket</SelectItem>
                <SelectItem value="pal24">Pal24</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Summary */}
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span>Plan:</span>
              <span className="font-medium">{plans?.find(p => p.id === selectedPlan)?.name || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span>Duration:</span>
              <span className="font-medium">{selectedDuration ? `${selectedDuration} days` : '-'}</span>
            </div>
            <div className="flex justify-between">
              <span>Payment:</span>
              <span className="font-medium">{selectedGateway || '-'}</span>
            </div>
            <div className="border-t pt-4">
              <Button 
                className="w-full" 
                onClick={handlePurchase}
                disabled={!selectedPlan || !selectedDuration || !selectedGateway}
              >
                Proceed to Payment
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

---

## Phase 3: Backend API (User Endpoints Only)

### 3.1 User API Endpoints

**File:** `src/api/endpoints/web_user.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from src.core.enums import PurchaseType
from src.infrastructure.database.models.dto import UserDto, SubscriptionDto, PlanDto, PaymentResult
from src.core.constants import USER_KEY
from src.services.subscription import SubscriptionService
from src.services.plan import PlanService
from src.services.payment_gateway import PaymentGatewayService
from src.services.promocode import PromocodeService
from src.services.referral import ReferralService
from src.services.partner import PartnerService
from src.services.user import UserService

router = APIRouter(prefix="/api/v1")


# ==============
# USER ENDPOINTS (Regular users only - NO ADMIN endpoints)
# ==============


@router.get("/user/me", response_model=UserDto)
async def get_current_user(user: UserDto = Depends()):
    """Get current authenticated user profile"""
    return user


# --- Subscription Endpoints ---

@router.get("/subscription/list", response_model=List[SubscriptionDto])
async def list_user_subscriptions(
    user: UserDto = Depends(),
    subscription_service: SubscriptionService = Depends(),
):
    """List all subscriptions for current user"""
    return await subscription_service.get_all_by_user(user.telegram_id)


@router.get("/subscription/{subscription_id}", response_model=SubscriptionDto)
async def get_user_subscription(
    subscription_id: int,
    user: UserDto = Depends(),
    subscription_service: SubscriptionService = Depends(),
):
    """Get specific subscription details (must belong to user)"""
    sub = await subscription_service.get(subscription_id)
    if not sub or sub.user_telegram_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.post("/subscription/purchase", response_model=PaymentResult)
async def purchase_subscription(
    plan_id: int,
    duration_days: int,
    gateway_type: str,
    user: UserDto = Depends(),
    plan_service: PlanService = Depends(),
    payment_service: PaymentGatewayService = Depends(),
):
    """Purchase new subscription (creates payment link)"""
    plan = await plan_service.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check plan availability for user
    available_plans = await plan_service.get_available_plans(user)
    if plan not in available_plans:
        raise HTTPException(status_code=403, detail="Plan not available for you")
    
    # Calculate pricing with user discounts
    pricing = calculate_pricing(plan, duration_days, user)
    
    # Create payment
    payment = await payment_service.create_payment(
        user=user,
        plan=plan,
        pricing=pricing,
        purchase_type=PurchaseType.NEW,
        gateway_type=gateway_type,
    )
    
    return payment


@router.post("/subscription/{subscription_id}/renew", response_model=PaymentResult)
async def renew_subscription(
    subscription_id: int,
    duration_days: int,
    gateway_type: str,
    user: UserDto = Depends(),
    subscription_service: SubscriptionService = Depends(),
    plan_service: PlanService = Depends(),
    payment_service: PaymentGatewayService = Depends(),
):
    """Renew existing subscription"""
    sub = await subscription_service.get(subscription_id)
    if not sub or sub.user_telegram_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    plan = await plan_service.get_by_tag(sub.plan.tag)
    pricing = calculate_pricing(plan, duration_days, user)
    
    payment = await payment_service.create_payment(
        user=user,
        plan=plan,
        pricing=pricing,
        purchase_type=PurchaseType.RENEW,
        gateway_type=gateway_type,
        renew_subscription_id=subscription_id,
    )
    
    return payment


@router.delete("/subscription/{subscription_id}")
async def delete_user_subscription(
    subscription_id: int,
    user: UserDto = Depends(),
    subscription_service: SubscriptionService = Depends(),
):
    """Delete user's own subscription"""
    sub = await subscription_service.get(subscription_id)
    if not sub or sub.user_telegram_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    await subscription_service.delete_subscription(subscription_id)
    return {"message": "Subscription deleted"}


# --- Plan Endpoints ---

@router.get("/plans", response_model=List[PlanDto])
async def list_available_plans(
    user: UserDto = Depends(),
    plan_service: PlanService = Depends(),
):
    """List plans available to current user"""
    return await plan_service.get_available_plans(user)


# --- Promocode Endpoints ---

@router.post("/promocode/activate")
async def activate_user_promocode(
    code: str,
    user: UserDto = Depends(),
    promocode_service: PromocodeService = Depends(),
    subscription_service: SubscriptionService = Depends(),
    user_service: UserService = Depends(),
):
    """Activate promocode for current user"""
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
    )
    
    if result.success:
        return {"message": "Promocode activated successfully"}
    else:
        raise HTTPException(status_code=400, detail=result.message_key)


# --- Referral Endpoints ---

@router.get("/referral/info")
async def get_user_referral_info(
    user: UserDto = Depends(),
    referral_service: ReferralService = Depends(),
):
    """Get current user's referral information"""
    ref_count = await referral_service.get_referral_count(user.telegram_id)
    reward_count = await referral_service.get_reward_count(user.telegram_id)
    ref_link = await referral_service.get_ref_link(user.referral_code)
    
    return {
        "referral_count": ref_count,
        "reward_count": reward_count,
        "referral_link": ref_link,
        "referral_code": user.referral_code,
        "points": user.points,
    }


# --- Partner Endpoints (User Side Only) ---

@router.get("/partner/info")
async def get_user_partner_info(
    user: UserDto = Depends(),
    partner_service: PartnerService = Depends(),
):
    """Get current user's partner information (if enrolled)"""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        raise HTTPException(status_code=404, detail="Not enrolled in partner program")
    
    stats = await partner_service.get_partner_statistics(partner)
    return stats


@router.get("/partner/earnings")
async def get_user_partner_earnings(
    user: UserDto = Depends(),
    partner_service: PartnerService = Depends(),
):
    """Get current user's partner earnings history"""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        raise HTTPException(status_code=404, detail="Not enrolled in partner program")
    
    transactions = await partner_service.get_partner_transactions(partner.id)
    return transactions


@router.post("/partner/withdraw")
async def request_user_partner_withdraw(
    amount: int,
    method: str,
    requisites: str,
    user: UserDto = Depends(),
    partner_service: PartnerService = Depends(),
    settings_service: SettingsService = Depends(),
):
    """Request withdrawal for current user (partner only)"""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        raise HTTPException(status_code=404, detail="Not enrolled in partner program")
    
    settings = await settings_service.get_partner_settings()
    
    withdrawal = await partner_service.request_withdrawal(
        partner=partner,
        amount=amount,
        method=method,
        requisites=requisites,
        settings=settings,
    )
    
    if not withdrawal:
        raise HTTPException(status_code=400, detail="Withdrawal request failed")
    
    return withdrawal
```

---

## Phase 4: Access Control

### 4.1 User-Only Middleware

**File:** `src/api/middlewares/user_access.py`

```python
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

async def user_access_middleware(request: Request, call_next):
    """
    Middleware to ensure web endpoints are user-only.
    Blocks admin/dev users from accessing web app (they should use Telegram).
    """
    # Get user from JWT token
    user = request.state.user
    
    # Block admin/dev users from web app
    if user.role in ['ADMIN', 'DEV']:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Admin/Dev users must use Telegram bot for management features"
            }
        )
    
    return await call_next(request)
```

### 4.2 Role-Based Access Control

```python
# In backend API routes

# User-only endpoints (web app)
@router.get("/user/me")
async def get_user(user: UserDto = Depends(get_current_user)):
    # Regular users only
    if user.role in [UserRole.ADMIN, UserRole.DEV]:
        raise HTTPException(403, "Use Telegram bot for admin features")
    return user

# NO admin endpoints in web API - all admin features stay in Telegram bot
```

---

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1** | 2 weeks | Auth system, project setup, Shadcn UI |
| **Phase 2** | 3 weeks | User features (Dashboard, Subscription, Purchase, Devices, Referrals, Partner) |
| **Phase 3** | 1 week | Backend API (user endpoints only) |
| **Phase 4** | 1 week | Database migrations, access control |
| **Phase 5** | 1 week | Telegram Mini App integration, testing |
| **Total** | **8 weeks** | User-facing web application |

---

## Key Differences from Previous Plan

| Aspect | Previous (Incorrect) | Current (Correct) |
|--------|---------------------|-------------------|
| **Scope** | Full app (user + admin) | USER ONLY |
| **Admin features** | Included in web | ❌ Telegram only |
| **Dashboard** | Admin dashboard | User dashboard only |
| **User management** | Web accessible | ❌ Telegram only |
| **Statistics** | Web accessible | ❌ Telegram only |
| **Settings** | All settings | User settings only |
| **API endpoints** | Full API | User API only |
| **Complexity** | High | Medium |
| **Timeline** | 12 weeks | 8 weeks |

---

## Security Notes

1. **Admin/Dev users are blocked from web app** - They must use Telegram bot
2. **Users can only access their own data** - All queries filtered by user ID
3. **No elevation of privilege** - Users cannot access admin features via web
4. **Same authentication** - Telegram OAuth for both web and bot

---

## References

- [React 19 Documentation](https://react.dev/learn)
- [Shadcn UI Documentation](https://ui.shadcn.com/docs)
- [Telegram Login Widget](https://core.telegram.org/widgets/login)
- [Telegram Web Apps](https://core.telegram.org/bots/webapps)
- [@telegram-apps/sdk](https://github.com/Telegram-Mini-Apps/telegram-apps)
