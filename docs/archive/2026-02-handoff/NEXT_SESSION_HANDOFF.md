# Bot ↔ Web Parity - Next Session Handoff Guide

**Created:** February 20, 2026  
**Current Status:** Phase B Complete ✅, Phase C 25% Complete 🔄  
**Next Session:** Phase C Continuation

---

## 🎯 Quick Start for Next Session

### 1. Start Backend

```bash
cd D:\altshop-0.9.3
uv run python -m src
```

Backend will be available at: `http://localhost:5000`

### 2. Generate OpenAPI Types

```bash
cd web-app
npm run generate:api
```

This will generate TypeScript types in `src/generated/`

### 3. Start Frontend Dev Server

```bash
cd web-app
npm run dev
```

Frontend will be available at: `http://localhost:5173`

---

## ✅ What's Complete

### Phase A: Foundation ✅ 100%
- Web routing verified
- Auth API unified
- API contract documented

### Phase B: Backend API ✅ 100%
- All 32 endpoints implemented
- All 5 services integrated
- Error handling complete

### Phase C: Frontend 🔄 25%
- ✅ OpenAPI generation setup
- ✅ PartnerPage withdrawals UI
- ⏳ PurchasePage (needs route fix)
- ⏳ ReferralsPage exchange flow
- ⏳ DashboardPage API integration
- ⏳ SettingsPage

---

## 📋 Remaining Tasks (Priority Order)

### 1. PurchasePage (3 hours) - HIGH PRIORITY

**File:** `web-app/src/pages/dashboard/PurchasePage.tsx`

**Issues to Fix:**
1. Route param mismatch - currently uses query param `?renew=1` but should use route `/subscription/:id/renew`
2. Multi-renew support - select multiple subscriptions to renew
3. Connect to generated API client

**Steps:**
```typescript
// 1. Update routing in App.tsx
<Route path="/dashboard/subscription/:id/renew" element={<PurchasePage />} />
<Route path="/dashboard/subscription/renew" element={<PurchasePage />} />

// 2. Update PurchasePage to use route params
const { id } = useParams()
const [searchParams] = useSearchParams()
const renewIds = searchParams.getAll('renew') // For multi-renew

// 3. Update API call
import { SubscriptionsService } from '@/generated'
const response = await SubscriptionsService.subscriptionPurchase({ ... })
```

**Acceptance Criteria:**
- [ ] Can renew single subscription
- [ ] Can renew multiple subscriptions
- [ ] Route params work correctly
- [ ] Payment flow completes successfully

---

### 2. ReferralsPage Exchange Flow (4 hours) - MEDIUM PRIORITY

**File:** `web-app/src/pages/dashboard/ReferralsPage.tsx`

**Features to Add:**
1. About section with FAQ
2. Points exchange flow
3. Exchange preview dialog
4. Exchange confirmation
5. Success/error states

**API Endpoints:**
```typescript
GET /api/v1/referral/exchange/options  // Get exchange types
POST /api/v1/referral/exchange/preview // Preview exchange
POST /api/v1/referral/exchange/confirm // Confirm exchange
```

**Exchange Types:**
- Days (points → subscription days)
- Gift (points → gift subscription)
- Discount (points → discount %)
- Traffic (points → additional traffic)

**UI Components Needed:**
```typescript
// ExchangeTypeSelector.tsx
// ExchangePreviewDialog.tsx
// ExchangeConfirmDialog.tsx
// ExchangeSuccessToast.tsx
```

**Acceptance Criteria:**
- [ ] About section displays correctly
- [ ] Can select exchange type
- [ ] Preview shows correct values
- [ ] Confirmation works
- [ ] Success/error toasts display

---

### 3. DashboardPage (2 hours) - MEDIUM PRIORITY

**File:** `web-app/src/pages/dashboard/DashboardPage.tsx`

**Changes Needed:**
1. Remove hardcoded metrics
2. Fetch real data from API
3. Add loading states
4. Error boundaries

**API Calls:**
```typescript
const { data: stats } = useQuery({
  queryKey: ['dashboard-stats'],
  queryFn: async () => {
    const [subs, devices, referrals] = await Promise.all([
      api.subscription.list(),
      // ... other calls
    ])
    return {
      activeSubscriptions: subs.filter(s => s.status === 'ACTIVE').length,
      // ...
    }
  }
})
```

**Acceptance Criteria:**
- [ ] Real metrics displayed
- [ ] Loading states work
- [ ] Error handling present
- [ ] Performance < 300ms

---

### 4. SettingsPage (3 hours) - LOW PRIORITY

**File:** `web-app/src/pages/dashboard/SettingsPage.tsx`

**Features to Implement:**
1. Profile settings form
2. Language selection
3. Notification preferences
4. Password change
5. Telegram link/unlink

**API Endpoints:**
```typescript
PATCH /api/v1/user/profile      // Update profile
PATCH /api/v1/user/password     // Change password
PATCH /api/v1/user/settings     // Update settings
POST /api/v1/user/link-telegram // Link Telegram
```

**Acceptance Criteria:**
- [ ] Profile form works
- [ ] Language changes apply
- [ ] Password change validates
- [ ] Telegram link status shown

---

### 5. Caching Layer (2 hours) - MEDIUM PRIORITY

**Files:** `web-app/src/lib/queryClient.ts` (NEW)

**Implementation:**
```typescript
// queryClient.ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000,   // 10 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
})

// Invalidate on mutations
queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
```

**Acceptance Criteria:**
- [ ] Cache configured
- [ ] Stale times set
- [ ] Invalidations work
- [ ] Performance improved

---

## 🔧 Common Issues & Solutions

### Issue 1: OpenAPI Generation Fails

**Error:** `Cannot connect to backend`

**Solution:**
```bash
# Check backend is running
curl http://localhost:5000/openapi.json

# If not running, start it
uv run python -m src
```

### Issue 2: Generated Types Don't Match

**Problem:** Backend changed but frontend types stale

**Solution:**
```bash
# Regenerate types
npm run generate:api

# Restart TypeScript server in VSCode
# Ctrl+Shift+P → "TypeScript: Restart TS Server"
```

### Issue 3: API Calls Fail with 401

**Problem:** Authentication token expired

**Solution:**
```typescript
// Check token in localStorage
console.log(localStorage.getItem('access_token'))

// Re-login if needed
await api.auth.login({ username, password })
```

### Issue 4: Route Params Not Working

**Problem:** `useParams()` returns undefined

**Solution:**
```typescript
// Ensure route is defined in App.tsx
<Route path="/dashboard/subscription/:id" element={<SubscriptionPage />} />

// Use params correctly
const { id } = useParams()
const subscriptionId = parseInt(id!)
```

---

## 📁 Key Files Reference

### Backend
- `src/api/endpoints/user.py` - Main API (1334 lines)
- `src/api/app.py` - FastAPI app setup
- `src/services/*` - Business logic

### Frontend
- `web-app/src/lib/api.ts` - API client
- `web-app/src/pages/dashboard/*` - Page components
- `web-app/src/types/index.ts` - TypeScript types
- `web-app/openapi-ts.config.json` - OpenAPI config

### Documentation
- `docs/API_CONTRACT.md` - API reference
- `docs/SERVICE_INTEGRATION_GUIDE.md` - Integration patterns
- `docs/TROUBLESHOOTING.md` - Debug guide
- `docs/PHASE_C_PROGRESS.md` - Current phase status

---

## 🧪 Testing Checklist

### Backend API Testing

```bash
# Test authentication
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Test subscriptions (with token)
curl -X GET http://localhost:5000/api/v1/subscription/list \
  --oauth2-bearer YOUR_TOKEN

# Test devices
curl -X GET "http://localhost:5000/api/v1/devices?subscription_id=1" \
  --oauth2-bearer YOUR_TOKEN
```

### Frontend Testing

```bash
# Run type check
npm run type-check

# Run linter
npm run lint

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## 📊 Progress Tracking Template

Copy this for daily progress:

```markdown
## [Date] Progress

### Completed Today
- [ ] Task 1
- [ ] Task 2

### In Progress
- [ ] Task 3 (50%)

### Blockers
- None / Describe issue

### Time Spent
- Total: X hours
- Backend: Xh
- Frontend: Xh
- Documentation: Xh

### Next Steps
1. Task 1
2. Task 2
```

---

## 🎯 Success Criteria for Phase C

Phase C is complete when:

- [x] OpenAPI generation setup
- [x] PartnerPage withdrawals UI
- [ ] PurchasePage routing fixed
- [ ] ReferralsPage exchange flow
- [ ] DashboardPage API integration
- [ ] SettingsPage implemented
- [ ] Caching layer added
- [ ] All pages use generated types
- [ ] Type errors < 10
- [ ] Performance score > 90

**Estimated Completion:** February 24-28, 2026

---

## 📞 Support Resources

### Documentation
- `docs/SESSION_COMPLETE_2026-02-20.md` - Latest session summary
- `docs/PHASE_C_PROGRESS.md` - Phase C status
- `docs/TROUBLESHOOTING.md` - Common issues

### Scripts
- `scripts/generate-api.sh` - Automated generation
- `web-app/package.json` - npm scripts

### Key Commands
```bash
# Backend
uv run python -m src

# Frontend
npm run dev
npm run generate:api
npm run build

# Testing
npm run type-check
npm run lint
```

---

## 🚀 Quick Wins for Next Session

If you want quick progress, start with:

1. **DashboardPage** (2h) - Straightforward API integration
2. **Caching Layer** (2h) - Copy/paste configuration
3. **PurchasePage route fix** (1h) - Simple param change

Then tackle the larger tasks:
4. **ReferralsPage** (4h) - Complex flow
5. **SettingsPage** (3h) - Multiple forms

---

**Handoff Created:** 2026-02-20 21:00 UTC  
**Status:** READY FOR CONTINUATION ✅  
**Confidence Level:** Very High 🟢

**Next Developer:** Pick up at any task above and go!
