# API Integration Troubleshooting Guide

**Version:** 1.0  
**Date:** 2026-02-20  
**Purpose:** Common issues and solutions for Bot ↔ Web parity implementation

---

## Recent Hotfix Notes (2026-02-24)

### Error: `Common:VAL_0001` with `paymentMethod` in Platega

**Symptoms (logs):**
```text
HTTP error creating Platega payment. Status: '400', Body: ... "key":"paymentMethod" ...
```

**Cause:** gateway setting `payment_method` was saved in unsupported format (legacy string/invalid value).

**Status:** Fixed.
- Canonicalization added: `1|CARD`, `2|SBP|SBPQR`
- Default switched to `2`
- Production payments are strict (clear configuration error)
- Test payments retry once with fallback to `2`
- Legacy DB values are auto-normalized on startup

**Quick check:**
```sql
SELECT id, type, settings->>'payment_method'
FROM payment_gateways
WHERE type='PLATEGA';
```

---

### Error: `TypeError: HeleketGateway requires HeleketGatewaySettingsDto`

**Cause:** malformed/undiscriminated settings payload caused wrong DTO type reconstruction.

**Status:** Fixed.
- `PaymentGateway.settings` uses discriminated union by `type`
- missing `settings.type` is injected from gateway type during parsing
- Heleket create flow uses v1-docs auth first, then controlled legacy fallback

---

### WATA H2H contract drift (`/api/h2h/*`)

**Cause:** runtime was using legacy assumptions while current API/webhook contract changed.

**Status:** Fixed.
- Base URL aligned to `https://api.wata.pro/api/h2h`
- Webhook parser supports new fields (`transactionId`, `transactionStatus`) with legacy fallback
- Status mapping aligned (`Paid`, `Declined`, `Created|Pending`)
- Mandatory `X-Signature` verification using the raw webhook body and the public key endpoint `/public-key`

---

### Error: `TypeError: 'traffic_used' is an invalid keyword argument for Subscription`

**Cause:** DTO-only fields (`traffic_used`, `devices_count`) were passed directly into SQLAlchemy `Subscription(...)`.

**Status:** Fixed in `src/services/subscription.py` by filtering persisted fields for both `create()` and `update()`.

---

### Error: `TypeError: got multiple values for keyword argument 'user_telegram_id'`

**Cause:** Subscription payload and explicit argument could both carry `user_telegram_id`.

**Status:** Fixed by excluding `user_telegram_id` from payload when constructing SQL model in `src/services/subscription.py`.

---

### Error: `UniqueViolationError: users_telegram_id_key`

**Cause:** Concurrent bot/web creation for the same Telegram user.

**Status:** Fixed with race-safe create logic in:
- `src/services/user.py` (`create`, `create_from_panel`)
- `src/services/auth.py` (`register`, `register_telegram_user`)

---

### Promocode sync mismatch (reward applied in DB but not in panel)

**Cause:** Promocode reward updates for duration/traffic/devices were saved locally without pushing to Remnawave.

**Status:** Fixed in `src/services/promocode.py` by syncing edited subscriptions through `remnawave_service.updated_user(...)` before local update commit.

---

## Quick Diagnostic Flowchart

```
API Not Working?
    │
    ├─ 401 Unauthorized? ──→ Check token in localStorage
    │                        └─→ Expired? → Check refresh logic
    │
    ├─ 403 Forbidden? ──→ Check resource ownership
    │                     └─→ User owns the resource?
    │
    ├─ 404 Not Found? ──→ Check URL path
    │                     ├─→ Using /api/v1/* prefix?
    │                     └─→ Resource exists in DB?
    │
    ├─ 500 Server Error? ──→ Check backend logs
    │                        └─→ Service method exists?
    │
    └─ CORS Error? ──→ Check nginx config
                       └─→ Backend CORS settings OK?
```

---

## Authentication Issues

### Problem: 401 Unauthorized on Every Request

**Symptoms:**
```typescript
// Frontend console
POST /api/v1/subscription/list → 401
Error: "Not authenticated"
```

**Possible Causes:**

1. **Token not in localStorage**
   ```javascript
   // Check
   console.log(localStorage.getItem('access_token'))
   // Should not be null
   ```

2. **Token expired**
   ```javascript
   // Token should refresh automatically
   // Check if refresh_token exists
   console.log(localStorage.getItem('refresh_token'))
   ```

3. **Wrong token format**
   ```javascript
   // Should be: "Bearer eyJhbGc..."
   // Check Authorization header
   const token = localStorage.getItem('access_token')
   console.log(`Bearer ${token}`)
   ```

**Solutions:**

```typescript
// 1. Re-login to get fresh tokens
await api.auth.login({ username, password })

// 2. Manually refresh
const refresh_token = localStorage.getItem('refresh_token')
const response = await axios.post('/api/v1/auth/refresh', { refresh_token })
localStorage.setItem('access_token', response.data.access_token)
localStorage.setItem('refresh_token', response.data.refresh_token)

// 3. Check API interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  console.log('Token:', token ? 'Present' : 'Missing')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

---

### Problem: Token Refresh Not Working

**Symptoms:**
```
POST /api/v1/auth/refresh → 401
Redirected to /auth/login
```

**Possible Causes:**

1. **Refresh token expired** (30 days)
2. **Wrong refresh token format**
3. **Backend refresh logic issue**

**Solutions:**

```typescript
// Debug refresh flow
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refresh_token')
      console.log('Refresh token:', refreshToken ? 'Present' : 'Missing')
      
      if (!refreshToken) {
        console.error('No refresh token - redirecting to login')
        window.location.href = '/auth/login'
        return
      }
      
      try {
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken
        })
        console.log('Refresh successful:', response.data)
      } catch (refreshError) {
        console.error('Refresh failed:', refreshError)
        localStorage.clear()
        window.location.href = '/auth/login'
      }
    }
  }
)
```

---

## Subscription Issues

### Problem: Purchase Returns 400 Bad Request

**Symptoms:**
```json
POST /api/v1/subscription/purchase
{
  "detail": "Plan not found"
}
```

**Possible Causes:**

1. **Plan ID doesn't exist**
2. **Plan is not active**
3. **Duration not available for plan**
4. **Gateway type not configured**

**Debug Steps:**

```python
# Backend logs
logger.info(f"Purchase request: {request}")
logger.info(f"Plan ID: {request.plan_id}")

# Check plan exists
plan = await plan_service.get(request.plan_id)
logger.info(f"Plan found: {plan is not None}")
logger.info(f"Plan active: {plan.is_active if plan else 'N/A'}")
logger.info(f"Plan durations: {plan.durations if plan else 'N/A'}")
```

**Solutions:**

```python
# 1. Verify plan exists in database
# Run in Python shell:
from src.services.plan import PlanService
plan = await plan_service.get(1)
print(plan)

# 2. Check plan is active
plan.is_active = True
await plan_service.update(plan)

# 3. Add duration to plan
# Via admin panel or database
```

---

### Problem: "Maximum subscriptions limit reached"

**Symptoms:**
```json
POST /api/v1/subscription/purchase
{
  "detail": "Maximum subscriptions limit reached (5)"
}
```

**Cause:** User has 5 active subscriptions (hard limit)

**Solutions:**

```python
# Option 1: Delete old subscriptions
from src.services.subscription import SubscriptionService
subs = await subscription_service.get_all_by_user(telegram_id)
for sub in subs:
    if sub.status == "DELETED":
        continue
    # Mark as deleted if not needed
    await subscription_service.delete_subscription(sub.id)

# Option 2: Increase limit (not recommended)
# Edit src/core/constants.py
MAX_SUBSCRIPTIONS_PER_USER = 10  # Was 5
```

**Frontend Prevention:**
```typescript
// Check before purchase
const { data: subscriptions } = useQuery({
  queryKey: ['subscriptions'],
  queryFn: () => api.subscription.list(),
})

const activeCount = subscriptions?.filter(
  s => s.status !== 'DELETED'
).length || 0

const canPurchase = activeCount < 5
```

---

## Device Management Issues

### Problem: Device Generation Returns 501 Not Implemented

**Symptoms:**
```json
POST /api/v1/devices/generate
{
  "detail": "Device generation not yet implemented"
}
```

**Cause:** Endpoint structure exists but service integration missing

**Solution:**

```python
# In src/api/endpoints/user.py - generate_device_link

# Add RemnawaveService integration
@router.post("/devices/generate", response_model=GenerateDeviceResponse)
@inject
async def generate_device_link(
    request: GenerateDeviceRequest,
    current_user: UserDto = Depends(get_current_user),
    subscription_service: FromDishka[SubscriptionService] = None,
    remnawave_service: FromDishka[RemnawaveService] = None,
) -> GenerateDeviceResponse:
    # Validate subscription
    subscription = await subscription_service.get(request.subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")
    
    # Check ownership
    if subscription.user_telegram_id != current_user.telegram_id:
        raise HTTPException(403, "Access denied")
    
    # Check device limit
    if subscription.devices_count >= subscription.device_limit:
        raise HTTPException(
            400,
            f"Device limit reached: {subscription.devices_count}/{subscription.device_limit}"
        )
    
    # Generate via Remnawave
    device_info = await remnawave_service.generate_device_key(
        user_remna_id=subscription.user_remna_id,
        device_type=request.device_type or DeviceType.ANDROID
    )
    
    return GenerateDeviceResponse(
        hwid=device_info.hwid,
        connection_url=device_info.connection_url,
        device_type=request.device_type or DeviceType.ANDROID
    )
```

---

### Problem: Device Revoke Not Working

**Symptoms:**
```
DELETE /api/v1/devices/{hwid} → 400
"Failed to revoke device"
```

**Debug Steps:**

```python
# Check RemnawaveService method exists
from src.services.remnawave import RemnawaveService

# Method should exist:
async def revoke_device(
    self,
    user_remna_id: UUID,
    hwid: str
) -> bool:
    """Revoke device in Remnawave panel."""
    # Implementation needed
```

**Solution:**

```python
# Add to src/services/remnawave.py

async def revoke_device(
    self,
    user_remna_id: UUID,
    hwid: str
) -> bool:
    """Revoke device access in Remnawave panel."""
    try:
        response = await self.remnawave.hwid_devices.delete_user_hwid_device(
            user_uuid=user_remna_id,
            hwid=hwid
        )
        
        if isinstance(response, DeleteUserHwidDeviceResponseDto):
            logger.info(f"Device {hwid} revoked for user {user_remna_id}")
            return True
        
        logger.warning(f"Unexpected response: {response}")
        return False
        
    except Exception as e:
        logger.exception(f"Failed to revoke device {hwid}: {e}")
        return False
```

---

## Promocode Issues

### Problem: Promocode Activation Always Returns Error

**Symptoms:**
```json
POST /api/v1/promocode/activate
{
  "detail": "Invalid promocode"
}
```

**Debug Steps:**

```python
# 1. Check promocode exists
promocode = await promocode_service.get_by_code("TESTCODE")
print(f"Found: {promocode is not None}")

# 2. Check promocode is active
print(f"Active: {promocode.is_active if promocode else 'N/A'}")

# 3. Check not expired
from datetime import datetime
print(f"Expires: {promocode.expires_at}")
print(f"Expired: {promocode.expires_at < datetime.now()}")

# 4. Check not depleted
print(f"Activations: {promocode.activation_count}/{promocode.max_activations}")
```

**Common Issues:**

1. **Promocode doesn't exist** → Create via admin panel
2. **Promocode expired** → Extend expiration date
3. **Max activations reached** → Increase limit or create new code
4. **Already activated by user** → User can only use once

---

## Referral Issues

### Problem: Referral Link Not Generating

**Symptoms:**
```json
GET /api/v1/referral/info
{
  "referral_link": "",
  "referral_code": ""
}
```

**Cause:** Bot username not configured

**Solution:**

```python
# In src/api/endpoints/user.py - get_referral_info

# Get bot username dynamically
from src.services.settings import SettingsService
settings = await settings_service.get()
bot_username = settings.bot_username or "remnabot"

# Or from config
from src.core.config import AppConfig
config = AppConfig()
bot_username = config.bot.username

# Generate link
referral_code = f"ref_{current_user.telegram_id}"
referral_link = f"https://t.me/{bot_username}?start={referral_code}"
```

---

## CORS Issues

### Problem: CORS Error in Browser Console

**Symptoms:**
```
Access to fetch at 'https://remnabot.2get.pro/api/v1/subscription/list' 
from origin 'https://remnabot.2get.pro' has been blocked by CORS policy
```

**Causes:**

1. **Nginx not proxying correctly**
2. **Backend CORS not configured**
3. **Wrong origin in CORS allowlist**

**Solutions:**

```python
# 1. Check backend CORS (src/api/app.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://remnabot.2get.pro",
        "http://localhost:5173",  # Dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Check nginx config
# Should NOT add CORS headers - let backend handle it
location /api/v1 {
    proxy_pass http://altshop:5000;
    # Don't add Access-Control-Allow-Origin here
}

# 3. Test CORS
curl -X OPTIONS https://remnabot.2get.pro/api/v1/subscription/list \
  -H "Origin: https://remnabot.2get.pro" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

---

## Database Issues

### Problem: Subscription Not Found

**Symptoms:**
```json
GET /api/v1/subscription/123
{
  "detail": "Subscription not found"
}
```

**Debug Steps:**

```python
# 1. Check subscription exists
from src.infrastructure.database.models.sql import Subscription
sub = await session.get(Subscription, 123)
print(f"Found: {sub is not None}")

# 2. Check user ownership
print(f"User ID: {sub.user_telegram_id if sub else 'N/A'}")
print(f"Expected: {current_user.telegram_id}")

# 3. Check not deleted
print(f"Status: {sub.status if sub else 'N/A'}")
# DELETED subscriptions should not be accessible
```

---

## Performance Issues

### Problem: Slow API Responses (>1s)

**Symptoms:**
```
GET /api/v1/subscription/list → 2.3s
GET /api/v1/referral/list → 1.8s
```

**Causes:**

1. **No database indexing**
2. **N+1 queries**
3. **No caching**

**Solutions:**

```python
# 1. Add database indexes
# In migration file
CREATE INDEX CONCURRENTLY idx_subscriptions_user_telegram_id 
ON subscriptions(user_telegram_id);

CREATE INDEX CONCURRENTLY idx_referrals_referrer 
ON referrals(referrer_telegram_id);

# 2. Use eager loading
# Instead of:
referrals = await referral_service.get_referrals(user_id)
for ref in referrals:
    user = await user_service.get(ref.telegram_id)  # N+1!

# Use:
referrals = await repository.referrals.get_with_users(user_id)

# 3. Add caching
from functools import lru_cache
from datetime import timedelta

@router.get("/referral/info")
async def get_referral_info(
    current_user: UserDto = Depends(get_current_user),
    redis_client: Redis = None,
):
    cache_key = f"referral:info:{current_user.telegram_id}"
    cached = await redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Build response
    response = {...}
    
    # Cache for 5 minutes
    await redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(response)
    )
    
    return response
```

---

## Logging & Debugging

### Enable Debug Logging

```python
# In backend
import logging
logging.getLogger("src.api").setLevel(logging.DEBUG)

# Add to endpoints
@router.get("/endpoint")
async def endpoint():
    logger.debug("Request received")
    logger.debug(f"Current user: {current_user.telegram_id}")
    # ...
    logger.debug(f"Response: {result}")
    return result
```

### Frontend Debugging

```typescript
// Enable API debugging
const apiClient = axios.create({
  baseURL: '/api/v1',
})

apiClient.interceptors.request.use((config) => {
  console.group('API Request')
  console.log('URL:', config.url)
  console.log('Method:', config.method)
  console.log('Headers:', config.headers)
  console.log('Data:', config.data)
  console.groupEnd()
  return config
})

apiClient.interceptors.response.use((response) => {
  console.group('API Response')
  console.log('Status:', response.status)
  console.log('Data:', response.data)
  console.groupEnd()
  return response
}, (error) => {
  console.group('API Error')
  console.error('Status:', error.response?.status)
  console.error('Data:', error.response?.data)
  console.error('Error:', error.message)
  console.groupEnd()
  return Promise.reject(error)
})
```

---

## Common Error Codes

| Error Code | Meaning | Common Fix |
|------------|---------|------------|
| `VALIDATION_ERROR` | Invalid request data | Check request body format |
| `AUTH_REQUIRED` | Not authenticated | Add Authorization header |
| `INVALID_TOKEN` | Token expired/invalid | Refresh token or re-login |
| `ACCESS_DENIED` | Not owner of resource | Check resource ownership |
| `NOT_FOUND` | Resource doesn't exist | Verify ID exists |
| `ALREADY_EXISTS` | Duplicate resource | Use different ID/name |
| `INVALID_STATE` | Resource in wrong state | Check resource status |
| `RATE_LIMITED` | Too many requests | Wait and retry |

---

## Getting Help

### Check These First

1. **API Contract** - `docs/API_CONTRACT.md`
2. **Service Integration Guide** - `docs/SERVICE_INTEGRATION_GUIDE.md`
3. **Backend Logs** - `logs/` directory
4. **Frontend Console** - Browser DevTools

### When Asking for Help

Include:
- ✅ Full error message
- ✅ Request/response body
- ✅ Backend logs (relevant lines)
- ✅ What you've already tried
- ✅ Expected vs actual behavior

Example:
```
Issue: Purchase endpoint returns 400

Request:
POST /api/v1/subscription/purchase
{
  "plan_id": 999,
  "duration_days": 30
}

Response:
{
  "detail": "Plan not found"
}

Expected: Plan should exist

Tried:
- Verified plan_id is correct
- Checked plan is active
- Looked at backend logs

Logs show:
"Plan 999 not found in database"

Question: How to create plan 999?
```

---

## Parity Hotfix Cases (2026-02-22)

### Problem: `TypeError: Subscription() got multiple values for keyword argument 'user_telegram_id'`

**Cause:** subscription creation passed `user_telegram_id` twice (from DTO dump and explicit arg).  
**Fix path:** `src/services/subscription.py` now excludes `user_telegram_id` from `model_dump(...)` and passes it once.

### Problem: `/api/v1/promocode/activate` multi-step flow is unclear

**Expected flow:**

1. Initial call:
```json
{ "code": "PROMO2026" }
```
2. If response is `next_step=SELECT_SUBSCRIPTION`, call again with:
```json
{ "code": "PROMO2026", "subscription_id": 123 }
```
3. If response is `next_step=CREATE_NEW`, call again with:
```json
{ "code": "PROMO2026", "create_new": true }
```

### Problem: Different subscription limits between panel/API/task workers

**Current effective limit path (single source of truth):**

1. `SettingsService.get_max_subscriptions_for_user(user)`  
2. User override (if set) -> global settings fallback  
3. Hard ceiling clamp: `MAX_SUBSCRIPTIONS_PER_USER = 5`

**Where enforced now:**

1. API purchase flow: `src/api/endpoints/user.py` (`/subscription/purchase`)
2. Background purchase task: `src/infrastructure/taskiq/tasks/subscriptions.py`
3. Remnawave user creation guard: `src/services/remnawave.py`

---

## Access Mode 403 Cases (Bot -> Web Parity)

### Problem: Web API started returning `403` after changing bot access mode

**Source of truth:** `SettingsService.get_access_mode()`.

**Symptoms:**
```json
{ "detail": "Access denied: ..." }
```

**Meaning of `detail`:**

- `Access denied: service is currently restricted`
  - Mode is `RESTRICTED` and user is not `DEV/ADMIN`.
  - Affects login and protected API routes.
- `Access denied: registration is currently disabled`
  - Mode is `REG_BLOCKED` for a new web user.
- `Access denied: invite-only registration`
  - Mode is `INVITED`, but referral code was not provided.
- `Access denied: valid invite code is required`
  - Mode is `INVITED`, referral code was provided, but invalid or self-referral.
- `Access denied: purchases are currently disabled`
  - Mode is `PURCHASE_BLOCKED` on purchase-scope routes.

**Purchase-scope routes:**
- `POST /api/v1/subscription/purchase`
- `POST /api/v1/subscription/{subscription_id}/renew`
- `POST /api/v1/subscription/trial`
- `POST /api/v1/promocode/activate`

**Quick checks:**
1. Verify mode in bot panel (`Режим доступа`).
2. Verify user role (DEV/ADMIN bypass applies).
3. For `INVITED`, verify referral:
   - normalized with `ref_` prefix,
   - referrer exists in DB,
   - not self-referral.

---

**Last Updated:** 2026-02-22  
**Maintained By:** Development Team
