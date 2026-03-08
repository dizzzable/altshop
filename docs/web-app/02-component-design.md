> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - Component Design

## Component Library Overview

This document defines all reusable components for the AltShop web application using **React 19.2.4** and **Shadcn UI**.

---

## Component Hierarchy

```
App
├── AuthProvider
│   └── Router
│       ├── PublicRoute
│       │   └── LoginPage
│       └── ProtectedRoute
│           └── DashboardLayout
│               ├── Header
│               ├── Sidebar (desktop) / MobileNav (mobile)
│               └── Main Content
│                   ├── DashboardPage
│                   ├── SubscriptionPage
│                   ├── PurchasePage
│                   ├── DevicesPage
│                   ├── ReferralsPage
│                   ├── PartnerPage
│                   ├── PromocodesPage
│                   └── SettingsPage
```

---

## Core Components

### 1. AuthProvider

**File:** `src/components/auth/AuthProvider.tsx`

```tsx
import { createContext, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';

interface User {
  telegram_id: number;
  username: string;
  name: string;
  role: 'USER' | 'ADMIN' | 'DEV';
  points: number;
  language: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user is authenticated on mount
    api.get('/user/me')
      .then(({ data }) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = () => {
    // Trigger Telegram OAuth
    window.location.href = '/auth/telegram';
  };

  const logout = async () => {
    await api.post('/api/v1/auth/logout');
    setUser(null);
    navigate('/auth/login');
  };

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

### 2. ProtectedRoute

**File:** `src/components/auth/ProtectedRoute.tsx`

```tsx
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
```

### 3. PublicRoute

**File:** `src/components/auth/PublicRoute.tsx`

```tsx
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';

interface PublicRouteProps {
  children: React.ReactNode;
}

export function PublicRoute({ children }: PublicRouteProps) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return <>{children}</>;
}
```

---

## Layout Components

### 4. DashboardLayout

**File:** `src/components/layout/DashboardLayout.tsx`

```tsx
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';

export function DashboardLayout() {
  return (
    <div className="min-h-screen bg-background">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile Header */}
      <div className="lg:hidden">
        <MobileNav />
      </div>

      {/* Main Content */}
      <div className="lg:pl-64">
        <Header />
        <main className="p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

### 5. Header

**File:** `src/components/layout/Header.tsx`

```tsx
import { useAuth } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Moon, Sun, LogOut, Settings, User } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center justify-between px-4">
        {/* Left: Page Title (shown on mobile) */}
        <div className="lg:hidden">
          <span className="text-sm font-medium">AltShop</span>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-4">
          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={user?.photo_url} alt={user?.name} />
                  <AvatarFallback>
                    {user?.name?.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{user?.name}</p>
                  <p className="text-xs leading-none text-muted-foreground">
                    @{user?.username}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate('/dashboard/settings')}>
                <User className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/dashboard/settings')}>
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
```

### 6. Sidebar

**File:** `src/components/layout/Sidebar.tsx`

```tsx
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  CreditCard,
  Smartphone,
  Users,
  Handshake,
  Ticket,
  Settings,
} from 'lucide-react';

const navItems = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    title: 'Subscription',
    href: '/dashboard/subscription',
    icon: CreditCard,
  },
  {
    title: 'Devices',
    href: '/dashboard/devices',
    icon: Smartphone,
  },
  {
    title: 'Referrals',
    href: '/dashboard/referrals',
    icon: Users,
  },
  {
    title: 'Partner',
    href: '/dashboard/partner',
    icon: Handshake,
  },
  {
    title: 'Promocodes',
    href: '/dashboard/promocodes',
    icon: Ticket,
  },
  {
    title: 'Settings',
    href: '/dashboard/settings',
    icon: Settings,
  },
];

export function Sidebar() {
  return (
    <div className="fixed inset-y-0 left-0 z-50 hidden w-64 flex-col border-r bg-background lg:flex">
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-6">
        <NavLink to="/dashboard" className="flex items-center gap-2 font-semibold">
          <span className="text-xl">🛡️</span>
          <span>AltShop</span>
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.title}
          </NavLink>
        ))}
      </nav>

      {/* User Info */}
      <div className="border-t p-4">
        <UserInfo />
      </div>
    </div>
  );
}
```

### 7. MobileNav

**File:** `src/components/layout/MobileNav.tsx`

```tsx
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { navItems } from './Sidebar';

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="lg:hidden">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-64">
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex h-14 items-center border-b">
            <NavLink 
              to="/dashboard" 
              className="flex items-center gap-2 font-semibold"
              onClick={() => setOpen(false)}
            >
              <span className="text-xl">🛡️</span>
              <span>AltShop</span>
            </NavLink>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-4">
            {navItems.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )
                }
                onClick={() => setOpen(false)}
              >
                <item.icon className="h-5 w-5" />
                {item.title}
              </NavLink>
            ))}
          </nav>
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

---

## Feature Components

### 8. SubscriptionCard

**File:** `src/components/features/subscription/SubscriptionCard.tsx`

```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Copy, Smartphone, RefreshCw, MoreVertical, Check, X } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { formatBytes, formatDays, formatPrice } from '@/lib/utils';
import { toast } from 'sonner';

interface SubscriptionCardProps {
  subscription: {
    id: number;
    status: 'ACTIVE' | 'EXPIRED' | 'LIMITED' | 'DISABLED';
    plan: {
      name: string;
      type: string;
    };
    traffic_limit: number;
    traffic_used: number;
    device_limit: number;
    devices_count: number;
    expire_at: string;
    url: string;
  };
  onRenew: (id: number) => void;
  onDelete: (id: number) => void;
}

export function SubscriptionCard({ subscription, onRenew, onDelete }: SubscriptionCardProps) {
  const statusConfig = {
    ACTIVE: { label: 'Active', variant: 'default' as const },
    EXPIRED: { label: 'Expired', variant: 'destructive' as const },
    LIMITED: { label: 'Limited', variant: 'warning' as const },
    DISABLED: { label: 'Disabled', variant: 'secondary' as const },
  };

  const config = statusConfig[subscription.status];

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{subscription.plan.name}</CardTitle>
            <p className="text-sm text-muted-foreground">{subscription.plan.type}</p>
          </div>
          <Badge variant={config.variant}>{config.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Traffic */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Traffic</span>
            <span>{formatBytes(subscription.traffic_used)} / {formatBytes(subscription.traffic_limit)}</span>
          </div>
          <Progress value={(subscription.traffic_used / subscription.traffic_limit) * 100} />
        </div>

        {/* Devices */}
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Devices</span>
          <div className="flex items-center gap-1">
            <Smartphone className="h-4 w-4" />
            <span>{subscription.devices_count} / {subscription.device_limit}</span>
          </div>
        </div>

        {/* Expiration */}
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Expires</span>
          <span className="font-medium">{formatDays(subscription.expire_at)}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(subscription.url);
              toast.success('Connection link copied!');
            }}
          >
            <Copy className="h-4 w-4 mr-1" />
            Copy Link
          </Button>
          
          {subscription.status === 'ACTIVE' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onRenew(subscription.id)}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Renew
            </Button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="ml-auto">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/dashboard/devices?sub=${subscription.id}`)}>
                <Smartphone className="h-4 w-4 mr-2" />
                Manage Devices
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => onDelete(subscription.id)}
                className="text-destructive"
              >
                <X className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}
```

### 9. PurchaseForm

**File:** `src/components/features/subscription/PurchaseForm.tsx`

```tsx
import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2 } from 'lucide-react';

interface PurchaseFormProps {
  plans: Plan[];
  gateways: Gateway[];
  onSubmit: (data: PurchaseData) => Promise<void>;
}

interface PurchaseData {
  plan_id: number;
  duration_days: number;
  gateway_type: string;
}

export function PurchaseForm({ plans, gateways, onSubmit }: PurchaseFormProps) {
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [selectedGateway, setSelectedGateway] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!selectedPlan || !selectedDuration || !selectedGateway) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        plan_id: selectedPlan,
        duration_days: selectedDuration,
        gateway_type: selectedGateway,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedPlanData = plans.find(p => p.id === selectedPlan);
  const selectedDurationData = selectedPlanData?.durations.find(d => d.days === selectedDuration);

  return (
    <div className="space-y-6">
      {/* Plan Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Select Plan</CardTitle>
          <CardDescription>Choose the plan that fits your needs</CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup value={selectedPlan?.toString()} onValueChange={(v) => setSelectedPlan(Number(v))}>
            {plans.map((plan) => (
              <div
                key={plan.id}
                className="flex items-center space-x-2 border rounded-lg p-4 cursor-pointer hover:bg-muted/50"
              >
                <RadioGroupItem value={plan.id.toString()} id={plan.id.toString()} />
                <Label htmlFor={plan.id.toString()} className="flex-1 cursor-pointer">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium">{plan.name}</p>
                      <p className="text-sm text-muted-foreground">{plan.description}</p>
                    </div>
                    <p className="text-sm font-medium">
                      {formatPrice(plan.durations[0]?.price)} {plan.durations[0]?.currency}
                    </p>
                  </div>
                  <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                    <span>📊 {formatBytes(plan.traffic_limit)}</span>
                    <span>📱 {plan.device_limit} devices</span>
                  </div>
                </Label>
              </div>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Duration Selection */}
      {selectedPlan && (
        <Card>
          <CardHeader>
            <CardTitle>Select Duration</CardTitle>
            <CardDescription>How long do you want the subscription?</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedDuration?.toString()} onValueChange={(v) => setSelectedDuration(Number(v))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose duration" />
              </SelectTrigger>
              <SelectContent>
                {selectedPlanData?.durations.map((duration) => (
                  <SelectItem key={duration.days} value={duration.days.toString()}>
                    {duration.days} days - {formatPrice(duration.price)} {duration.currency}
                    {duration.discount > 0 && (
                      <span className="text-green-600 text-xs ml-2">
                        Save {duration.discount}%
                      </span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      )}

      {/* Payment Method */}
      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>Choose how you want to pay</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedGateway} onValueChange={setSelectedGateway}>
            <SelectTrigger>
              <SelectValue placeholder="Choose payment method" />
            </SelectTrigger>
            <SelectContent>
              {gateways.filter(g => g.is_active).map((gateway) => (
                <SelectItem key={gateway.type} value={gateway.type}>
                  {gateway.type.replace('_', ' ')}
                </SelectItem>
              ))}
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
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Plan</span>
            <span className="font-medium">
              {selectedPlanData?.name || '-'}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Duration</span>
            <span className="font-medium">
              {selectedDuration ? `${selectedDuration} days` : '-'}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Payment</span>
            <span className="font-medium">
              {selectedGateway || '-'}
            </span>
          </div>
          <div className="border-t pt-4">
            <div className="flex justify-between font-semibold">
              <span>Total</span>
              <span>
                {selectedDurationData 
                  ? `${formatPrice(selectedDurationData.price)} ${selectedDurationData.currency}`
                  : '-'
                }
              </span>
            </div>
          </div>
          <Button 
            className="w-full" 
            onClick={handleSubmit}
            disabled={!selectedPlan || !selectedDuration || !selectedGateway || isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              'Proceed to Payment'
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 10. ReferralLink

**File:** `src/components/features/referrals/ReferralLink.tsx`

```tsx
import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Copy, Share2, QrCode, Check } from 'lucide-react';
import { toast } from 'sonner';

interface ReferralLinkProps {
  link: string;
  code: string;
}

export function ReferralLink({ link, code }: ReferralLinkProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(link);
    setCopied(true);
    toast.success('Link copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Join me on AltShop',
          text: 'Get VPN subscription with my referral link',
          url: link,
        });
      } catch (err) {
        console.error('Share failed:', err);
      }
    } else {
      handleCopy();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your Referral Link</CardTitle>
        <CardDescription>Share this link to earn rewards</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input value={link} readOnly className="font-mono text-sm" />
          <Button onClick={handleCopy} size="icon">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
          <Button onClick={handleShare} size="icon" variant="outline">
            <Share2 className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1">
            <QrCode className="h-4 w-4 mr-2" />
            Show QR Code
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

---

## Component Index

**File:** `src/components/index.ts`

```tsx
// Auth
export { AuthProvider, useAuth } from './auth/AuthProvider';
export { ProtectedRoute } from './auth/ProtectedRoute';
export { PublicRoute } from './auth/PublicRoute';
export { TelegramLogin } from './auth/TelegramLogin';

// Layout
export { DashboardLayout } from './layout/DashboardLayout';
export { Header } from './layout/Header';
export { Sidebar } from './layout/Sidebar';
export { MobileNav } from './layout/MobileNav';
export { UserInfo } from './layout/UserInfo';

// Features - Subscription
export { SubscriptionCard } from './features/subscription/SubscriptionCard';
export { SubscriptionList } from './features/subscription/SubscriptionList';
export { PurchaseForm } from './features/subscription/PurchaseForm';
export { RenewForm } from './features/subscription/RenewForm';

// Features - Devices
export { DeviceCard } from './features/devices/DeviceCard';
export { DeviceList } from './features/devices/DeviceList';
export { GenerateLinkDialog } from './features/devices/GenerateLinkDialog';

// Features - Referrals
export { ReferralLink } from './features/referrals/ReferralLink';
export { ReferralStats } from './features/referrals/ReferralStats';
export { ReferralList } from './features/referrals/ReferralList';

// Features - Partner
export { PartnerStats } from './features/partner/PartnerStats';
export { PartnerEarnings } from './features/partner/PartnerEarnings';
export { WithdrawForm } from './features/partner/WithdrawForm';

// Features - Promocodes
export { PromocodeForm } from './features/promocodes/PromocodeForm';

// UI (re-export from shadcn)
export { Button } from '@/components/ui/button';
export { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
export { Input } from '@/components/ui/input';
export { Label } from '@/components/ui/label';
export { Badge } from '@/components/ui/badge';
export { Progress } from '@/components/ui/progress';
export { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
export { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
export { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
export { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
export { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
export { Skeleton } from '@/components/ui/skeleton';
export { Toast, Toaster } from '@/components/ui/toast';
```

---

## Next Steps

1. **Create all component files** in the specified structure
2. **Install Shadcn UI components** via CLI
3. **Install Lucide React** for icons
4. **Test each component** in isolation
5. **Create Storybook** for component documentation (optional)
6. **Implement responsive design** for all components
7. **Add accessibility** attributes (ARIA labels, keyboard navigation)
