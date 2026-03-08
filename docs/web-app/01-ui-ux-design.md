> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - UI/UX Design Specification

## Design System Overview

### Brand Identity

| Attribute | Value |
|-----------|-------|
| **Primary Color** | `#3B82F6` (Blue 500) |
| **Secondary Color** | `#10B981` (Emerald 500) |
| **Accent Color** | `#8B5CF6` (Violet 500) |
| **Background** | `#FFFFFF` (Light) / `#0F172A` (Dark) |
| **Text Primary** | `#1E293B` (Light) / `#F8FAFC` (Dark) |
| **Font Family** | Inter, system-ui, sans-serif |

### Design Principles

1. **Clean & Minimal** - Focus on content, reduce clutter
2. **Mobile-First** - Designed for mobile, enhanced for desktop
3. **Accessible** - WCAG 2.1 AA compliance
4. **Consistent** - Reusable components, predictable patterns
5. **Fast** - Optimized for performance

---

## Color Palette

### Light Theme

```css
:root {
  /* Primary */
  --primary: 221.2 83.2% 53.3%;      /* #3B82F6 */
  --primary-foreground: 210 40% 98%;  /* White */
  
  /* Secondary */
  --secondary: 160 84% 39%;           /* #10B981 */
  --secondary-foreground: 210 40% 98%;
  
  /* Accent */
  --accent: 262.1 83.3% 57.8%;        /* #8B5CF6 */
  --accent-foreground: 210 40% 98%;
  
  /* Destructive */
  --destructive: 0 84.2% 60.2%;       /* #EF4444 */
  --destructive-foreground: 210 40% 98%;
  
  /* Background */
  --background: 0 0% 100%;            /* #FFFFFF */
  --foreground: 222.2 84% 4.9%;       /* #0F172A */
  
  /* Muted */
  --muted: 210 40% 96.1%;             /* #F1F5F9 */
  --muted-foreground: 215.4 16.3% 46.9%;
  
  /* Card */
  --card: 0 0% 100%;
  --card-foreground: 222.2 84% 4.9%;
  
  /* Border */
  --border: 214.3 31.8% 91.4%;        /* #E2E8F0 */
  
  /* Ring */
  --ring: 221.2 83.2% 53.3%;
}
```

### Dark Theme

```css
.dark {
  --background: 222.2 84% 4.9%;       /* #0F172A */
  --foreground: 210 40% 98%;          /* #F8FAFC */
  
  --primary: 217.2 91.2% 59.8%;       /* #3B82F6 */
  --primary-foreground: 222.2 84% 4.9%;
  
  --secondary: 160 84% 39%;
  --secondary-foreground: 210 40% 98%;
  
  --muted: 217.2 32.6% 17.5%;         /* #1E293B */
  --muted-foreground: 215 20.2% 65.1%;
  
  --card: 222.2 84% 4.9%;
  --card-foreground: 210 40% 98%;
  
  --border: 217.2 32.6% 17.5%;
  --ring: 224.3 76.3% 48%;
}
```

### Status Colors

| Status | Color | Usage |
|--------|-------|-------|
| Active | `#10B981` | Active subscriptions |
| Expired | `#EF4444` | Expired subscriptions |
| Limited | `#F59E0B` | Traffic limit exceeded |
| Disabled | `#6B7280` | Disabled subscriptions |
| Pending | `#F59E0B` | Pending payments/withdrawals |
| Success | `#10B981` | Success messages |
| Error | `#EF4444` | Error messages |
| Info | `#3B82F6` | Info messages |

---

## Typography

### Font Stack

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 
             'Roboto', 'Helvetica', 'Arial', sans-serif;
```

### Type Scale

| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| H1 | 2rem (32px) | 700 | 1.2 |
| H2 | 1.5rem (24px) | 600 | 1.3 |
| H3 | 1.25rem (20px) | 600 | 1.4 |
| H4 | 1.125rem (18px) | 500 | 1.4 |
| Body | 1rem (16px) | 400 | 1.5 |
| Small | 0.875rem (14px) | 400 | 1.5 |
| Caption | 0.75rem (12px) | 400 | 1.4 |

---

## Spacing System

Based on 4px grid:

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 0.25rem (4px) | Tight spacing |
| `space-2` | 0.5rem (8px) | Icon gaps |
| `space-3` | 0.75rem (12px) | Component padding |
| `space-4` | 1rem (16px) | Standard spacing |
| `space-5` | 1.25rem (20px) | Section spacing |
| `space-6` | 1.5rem (24px) | Card padding |
| `space-8` | 2rem (32px) | Section margins |
| `space-10` | 2.5rem (40px) | Large gaps |
| `space-12` | 3rem (48px) | Page sections |
| `space-16` | 4rem (64px) | Major sections |

---

## Component Specifications

### 1. Button

```tsx
// Variants
- default (primary blue)
- secondary (gray)
- destructive (red)
- outline (border only)
- ghost (transparent)
- link (text only)

// Sizes
- sm: h-9 px-3 text-xs
- default: h-10 px-4 py-2
- lg: h-11 px-8 text-base
- icon: h-10 w-10

// States
- default
- hover (brightness +10%)
- active (brightness -10%)
- disabled (opacity 50%)
- loading (spinner + disabled)
```

**Usage Examples:**
```tsx
// Primary action
<Button>Purchase Subscription</Button>

// Secondary action
<Button variant="outline">Cancel</Button>

// Destructive action
<Button variant="destructive">Delete</Button>

// Icon button
<Button size="icon"><CopyIcon /></Button>
```

### 2. Card

```tsx
// Structure
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Description</CardDescription>
  </CardHeader>
  <CardContent>Content</CardContent>
  <CardFooter>Footer actions</CardFooter>
</Card>

// Variants
- default (border + shadow)
- elevated (shadow only)
- outlined (border only)
```

### 3. Input

```tsx
// Types
- text
- email
- password
- number
- search
- textarea

// States
- default
- focus (ring)
- error (red border)
- disabled (opacity 50%)
- with icon
- with label
- with error message
```

### 4. Badge

```tsx
// Variants
- default (blue)
- secondary (gray)
- destructive (red)
- outline (border)
- success (green)
- warning (yellow)

// Sizes
- sm: text-xs
- default: text-sm
```

### 5. Table

```tsx
// Structure
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Header</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell>Cell</TableCell>
    </TableRow>
  </TableBody>
</Table>

// Features
- sortable columns
- row selection
- pagination
- sticky header
```

---

## Page Layouts

### 1. Authentication Page (`/auth/login`)

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │           🛡️  AltShop Web                          │    │
│  │                                                     │    │
│  │         Manage your VPN subscription               │    │
│  │                                                     │    │
│  │  ┌───────────────────────────────────────────┐    │    │
│  │  │                                            │    │    │
│  │  │      [Telegram Login Widget]              │    │    │
│  │  │                                            │    │    │
│  │  └───────────────────────────────────────────┘    │    │
│  │                                                     │    │
│  │  ✓ Secure authentication via Telegram              │    │
│  │  ✓ No password required                            │    │
│  │  ✓ Instant access to your account                  │    │
│  │                                                     │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:**
```
┌─────────────────────┐
│                     │
│   🛡️ AltShop       │
│                     │
│  Manage your VPN    │
│   subscription      │
│                     │
│ ┌─────────────────┐ │
│ │                 │ │
│ │ [Telegram Btn]  │ │
│ │                 │ │
│ └─────────────────┘ │
│                     │
│ ✓ Secure           │
│ ✓ No password      │
│ ✓ Instant access   │
│                     │
└─────────────────────┘
```

### 2. User Dashboard (`/dashboard`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                                    👤 John Doe       ⚙️  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Welcome back, John! 👋                                              │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Status    │  │   Active    │  │   Points    │                 │
│  │   🟢 Active │  │   Subs: 2   │  │   💎 150    │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                      │
│  Quick Actions                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ ➕ Purchase │  │ 🔄 Renew    │  │ 📱 Devices  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                      │
│  My Subscriptions                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🟢 Premium Plan                              Expires in 25d  │   │
│  │    50GB / 100GB used                          [Manage →]    │   │
│  │    2 / 3 devices                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🔴 Basic Plan                               Expired 5d ago   │   │
│  │    0GB / 20GB used                            [Renew →]     │   │
│  │    0 / 1 devices                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Subscription List (`/dashboard/subscription`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                              Subscriptions           [+ Purchase] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Filters: [All ▼] [Status ▼] [Plan ▼]                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🟢 Premium Plan                              Active         │   │
│  │ ─────────────────────────────────────────────────────────── │   │
│  │ Traffic: ████████░░ 80GB/100GB                              │   │
│  │ Devices: ●●●○○○ 3/5                                         │   │
│  │ Expires: March 15, 2026 (25 days)                           │   │
│  │                                                             │   │
│  │ [📋 Copy Link]  [📱 Devices]  [🔄 Renew]  [⋮ More]        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🔴 Basic Plan                               Expired         │   │
│  │ ─────────────────────────────────────────────────────────── │   │
│  │ Traffic: ░░░░░░░░░░ 0GB/20GB                                │   │
│  │ Devices: ○○○○○ 0/1                                          │   │
│  │ Expired: February 13, 2026 (5 days ago)                     │   │
│  │                                                             │   │
│  │ [📋 Copy Link]  [📱 Devices]  [🔄 Renew]  [⋮ More]        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. Purchase Flow (`/dashboard/subscription/purchase`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                    Purchase Subscription        [Back]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: Select Plan           Step 2: Duration    Step 3: Payment  │
│  ────────────────────────────────────────────────────────────────   │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │ ○ Basic         │  │ ○ Standard      │  │ ● Premium       │     │
│  │   20GB          │  │   50GB          │  │   100GB         │     │
│  │   1 device      │  │   3 devices     │  │   5 devices     │     │
│  │   $4.99/mo      │  │   $9.99/mo      │  │   $14.99/mo     │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                      │
│  Duration: [30 days ▼]                                              │
│                                                                      │
│  Payment Method: [Telegram Stars ▼]                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Summary                                                      │   │
│  │ ─────────────────────────────────────────────────────────── │   │
│  │ Plan: Premium (100GB, 5 devices)                            │   │
│  │ Duration: 30 days                                           │   │
│  │ Payment: Telegram Stars                                     │   │
│  │ ─────────────────────────────────────────────────────────── │   │
│  │ Total: 500 ★                                                │   │
│  │                                                             │   │
│  │ [Proceed to Payment →]                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5. Devices Management (`/dashboard/devices`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                              My Devices              [+ Add] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Subscription: [Premium Plan ▼]                                     │
│  Used: 3 / 5 devices                                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 📱 iPhone 14 Pro                            Added: Jan 15   │   │
│  │    Last seen: 2 hours ago                      [Revoke ❌]  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 💻 MacBook Pro                               Added: Feb 1   │   │
│  │    Last seen: 5 minutes ago                    [Revoke ❌]  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🖥️ Windows PC                               Added: Feb 10   │   │
│  │    Last seen: 3 days ago                       [Revoke ❌]  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Available slots: 2                                                 │
│  [Generate New Connection Link]                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6. Referral Program (`/dashboard/referrals`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                              Referrals                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Invite friends and earn rewards!                           │   │
│  │                                                             │   │
│  │  Your referral link:                                        │   │
│  │  ┌─────────────────────────────────────────────────────┐   │   │
│  │  │ https://t.me/altshop_bot?start=ref_ABC123           │   │   │
│  │  └─────────────────────────────────────────────────────┘   │   │
│  │  [📋 Copy]  [📤 Share]  [🧾 QR Code]                       │   │
│  │                                                             │   │
│  │  Rewards: 10 points per referral                            │   │
│  │  Your points: 💎 150                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Statistics                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Total     │  │   Active    │  │   Earned    │                 │
│  │   25        │  │   18        │  │   250 pts   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                      │
│  Recent Referrals                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ @john_d                    Joined: Feb 15    ✅ Active      │   │
│  │ @jane_smith                Joined: Feb 14    ✅ Active      │   │
│  │ @bob_wilson                Joined: Feb 10    ⏳ Inactive    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 7. Settings (`/dashboard/settings`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ☰  AltShop                              Settings                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Profile                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 👤 John Doe                                                  │   │
│  │    @johndoe                                                  │   │
│  │    ID: 123456789                                             │   │
│  │                                                              │   │
│  │    [Edit Profile]                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Preferences                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Language: [English ▼]                                        │   │
│  │                                                              │   │
│  │ Notifications:                                               │   │
│  │   ☑ Subscription expiring                                    │   │
│  │   ☑ Traffic limit reached                                    │   │
│  │   ☐ Promotional messages                                     │   │
│  │                                                              │   │
│  │ Theme: [○ Light  ● Dark  ○ System]                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Security                                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Active sessions: 2                                           │   │
│  │                                                              │   │
│  │ [View Sessions]  [Logout All]                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Account                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ [Download My Data]                                           │   │
│  │ [Delete Account]                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| `sm` | 640px | Mobile landscape |
| `md` | 768px | Tablet portrait |
| `lg` | 1024px | Tablet landscape |
| `xl` | 1280px | Desktop |
| `2xl` | 1536px | Large desktop |

### Mobile-First Approach

```tsx
// Default: Mobile styles
<div className="flex flex-col gap-4 p-4">
  {/* Content */}
</div>

// Tablet and up
<div className="md:flex md:flex-row md:gap-6 md:p-6">
  {/* Content */}
</div>

// Desktop and up
<div className="lg:gap-8 lg:p-8">
  {/* Content */}
</div>
```

---

## Animation Guidelines

### Duration

| Animation | Duration | Easing |
|-----------|----------|--------|
| Fade in/out | 150ms | ease-in-out |
| Slide in/out | 200ms | ease-out |
| Scale | 150ms | ease-out |
| Button hover | 100ms | ease |
| Loading spinner | 1s | linear (infinite) |

### Examples

```css
/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Slide up */
@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* Pulse (loading) */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

---

## Icon System

Using [Lucide React](https://lucide.dev/) icons:

| Icon | Usage |
|------|-------|
| `LayoutDashboard` | Dashboard |
| `CreditCard` | Subscription |
| `Smartphone` | Devices |
| `Users` | Referrals |
| `Handshake` | Partner |
| `Ticket` | Promocodes |
| `Settings` | Settings |
| `Copy` | Copy link |
| `Check` | Success |
| `X` | Error/Close |
| `Loader2` | Loading |
| `ChevronRight` | Navigation |
| `LogOut` | Logout |
| `Moon/Sun` | Theme toggle |
| `Menu` | Mobile menu |

---

## Accessibility Requirements

### WCAG 2.1 AA Compliance

1. **Color Contrast**
   - Text: minimum 4.5:1 ratio
   - Large text: minimum 3:1 ratio
   - UI components: minimum 3:1 ratio

2. **Keyboard Navigation**
   - All interactive elements focusable
   - Visible focus indicators
   - Logical tab order

3. **Screen Reader Support**
   - Semantic HTML
   - ARIA labels where needed
   - Alt text for images

4. **Motion**
   - Respect `prefers-reduced-motion`
   - No auto-playing animations

---

## File Structure

```
src/
├── components/
│   ├── ui/                    # Shadcn primitives
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   ├── MobileNav.tsx
│   │   └── Sidebar.tsx
│   └── features/
│       ├── subscription/
│       │   ├── SubscriptionCard.tsx
│       │   ├── SubscriptionList.tsx
│       │   └── PurchaseForm.tsx
│       ├── devices/
│       │   ├── DeviceCard.tsx
│       │   └── DeviceList.tsx
│       └── referrals/
│           ├── ReferralLink.tsx
│           └── ReferralStats.tsx
├── pages/
│   ├── auth/
│   │   └── Login.tsx
│   ├── dashboard/
│   │   ├── Dashboard.tsx
│   │   ├── SubscriptionPage.tsx
│   │   ├── PurchasePage.tsx
│   │   ├── DevicesPage.tsx
│   │   ├── ReferralsPage.tsx
│   │   ├── PartnerPage.tsx
│   │   ├── PromocodesPage.tsx
│   │   └── SettingsPage.tsx
│   └── NotFound.tsx
└── styles/
    ├── globals.css
    └── themes.css
```

---

## Next Steps

1. **Set up Shadcn UI** with custom theme
2. **Create base components** (Button, Card, Input, etc.)
3. **Implement layout components** (Header, Sidebar, etc.)
4. **Build feature components** (Subscription, Devices, etc.)
5. **Create page layouts** following mockups
6. **Add animations** and transitions
7. **Test accessibility** and fix issues
8. **Optimize for mobile** performance
