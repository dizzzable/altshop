> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - API Design

## Base URL

```
Production: https://bot.domain.com/api/v1
Development: http://localhost:5000/api/v1
```

---

## Authentication Endpoints

### POST `/auth/telegram`

Authenticate user via Telegram OAuth.

**Request:**
```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "photo_url": "https://t.me/i/userpic/320/...",
  "auth_date": 1708272000,
  "hash": "abc123..."
}
```

**Response (200 OK):**
```json
{
  "expires_in": 604800,
  "is_new_user": false,
  "auth_source": "WEB_TELEGRAM_WEBAPP"
}
```

Session is established via HttpOnly cookies.

**Errors:**
- `401` - Invalid hash or expired auth_date

---

### POST `/api/v1/auth/refresh`

Refresh access token.

**Request:** empty body, refresh cookie required

**Response (200 OK):**
```json
{
  "expires_in": 604800
}
```

---

### POST `/api/v1/auth/logout`

Logout user (invalidate token).

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

---

## User Endpoints

### GET `/user/me`

Get current user profile.

**Response (200 OK):**
```json
{
  "telegram_id": 123456789,
  "username": "johndoe",
  "name": "John Doe",
  "role": "USER",
  "points": 150,
  "language": "en",
  "personal_discount": 5,
  "purchase_discount": 0,
  "is_blocked": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Subscription Endpoints

### GET `/subscription/list`

List all user subscriptions.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "status": "ACTIVE",
    "is_trial": false,
    "traffic_limit": 107374182400,
    "traffic_used": 85899345920,
    "device_limit": 5,
    "devices_count": 3,
    "expire_at": "2026-03-15T10:30:00Z",
    "url": "https://remna.example.com/key/abc123",
    "plan": {
      "id": 1,
      "name": "Premium",
      "type": "BOTH",
      "traffic_limit": 107374182400,
      "device_limit": 5
    }
  }
]
```

---

### GET `/subscription/{id}`

Get subscription details.

**Response (200 OK):**
```json
{
  "id": 1,
  "status": "ACTIVE",
  "is_trial": false,
  "traffic_limit": 107374182400,
  "traffic_used": 85899345920,
  "device_limit": 5,
  "devices_count": 3,
  "internal_squads": ["uuid-1", "uuid-2"],
  "external_squad": "uuid-3",
  "expire_at": "2026-03-15T10:30:00Z",
  "url": "https://remna.example.com/key/abc123",
  "device_type": "IPHONE",
  "plan": {
    "id": 1,
    "name": "Premium",
    "tag": "premium",
    "type": "BOTH",
    "traffic_limit": 107374182400,
    "device_limit": 5,
    "duration": 30
  }
}
```

---

### POST `/subscription/purchase`

Create new subscription purchase (returns payment link).

**Request:**
```json
{
  "plan_id": 1,
  "duration_days": 30,
  "gateway_type": "telegram_stars",
  "purchase_type": "NEW"
}
```

**Response (200 OK):**
```json
{
  "payment_id": "uuid-123",
  "url": "https://t.me/invoice/abc123"
}
```

**Errors:**
- `400` - Invalid plan or duration
- `403` - Plan not available for user
- `404` - Plan not found

---

### POST `/subscription/{id}/renew`

Renew existing subscription.

**Request:**
```json
{
  "duration_days": 30,
  "gateway_type": "telegram_stars"
}
```

**Response (200 OK):**
```json
{
  "payment_id": "uuid-123",
  "url": "https://t.me/invoice/abc123"
}
```

---

### DELETE `/subscription/{id}`

Delete subscription.

**Response (200 OK):**
```json
{
  "message": "Subscription deleted successfully"
}
```

---

## Plan Endpoints

### GET `/plans`

List available plans for current user.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "name": "Basic",
    "description": "Perfect for individuals",
    "type": "TRAFFIC",
    "availability": "ALL",
    "traffic_limit": 21474836480,
    "device_limit": 1,
    "is_active": true,
    "durations": [
      {
        "days": 30,
        "prices": [
          {
            "gateway_type": "TELEGRAM_STARS",
            "price": 200,
            "currency": "XTR"
          },
          {
            "gateway_type": "YOOKASSA",
            "price": 299,
            "currency": "RUB"
          }
        ]
      },
      {
        "days": 90,
        "prices": [
          {
            "gateway_type": "TELEGRAM_STARS",
            "price": 500,
            "currency": "XTR",
            "discount": 17
          }
        ]
      }
    ]
  }
]
```

---

## Promocode Endpoints

### POST `/promocode/activate`

Activate promocode.

**Request:**
```json
{
  "code": "SUMMER2024"
}
```

**Response (200 OK):**
```json
{
  "message": "Promocode activated successfully",
  "reward": {
    "type": "DURATION",
    "value": 7
  }
}
```

**Errors:**
- `400` - Invalid code, expired, or already used
- `404` - Promocode not found

---

## Referral Endpoints

### GET `/referral/info`

Get referral information.

**Response (200 OK):**
```json
{
  "referral_count": 25,
  "reward_count": 18,
  "referral_link": "https://t.me/altshop_bot?start=ref_ABC123",
  "referral_code": "ABC123",
  "points": 150
}
```

---

### GET `/referral/list`

List user's referrals.

**Query Parameters:**
- `page` (default: 1)
- `limit` (default: 20)

**Response (200 OK):**
```json
{
  "total": 25,
  "page": 1,
  "limit": 20,
  "referrals": [
    {
      "telegram_id": 987654321,
      "username": "friend1",
      "name": "Friend One",
      "level": 1,
      "joined_at": "2024-02-15T10:30:00Z",
      "is_active": true,
      "rewards_earned": 10
    }
  ]
}
```

---

## Partner Endpoints

### GET `/partner/info`

Get partner information.

**Response (200 OK):**
```json
{
  "is_partner": true,
  "balance": 5000,
  "total_earned": 15000,
  "total_withdrawn": 10000,
  "referrals_count": 10,
  "level2_referrals_count": 5,
  "level3_referrals_count": 2
}
```

**Errors:**
- `404` - User is not a partner

---

### GET `/partner/earnings`

List partner earnings.

**Query Parameters:**
- `page` (default: 1)
- `limit` (default: 20)

**Response (200 OK):**
```json
{
  "total": 50,
  "page": 1,
  "limit": 20,
  "earnings": [
    {
      "id": 1,
      "referral_telegram_id": 987654321,
      "referral_username": "friend1",
      "level": 1,
      "payment_amount": 299,
      "percent": 10,
      "earned_amount": 30,
      "created_at": "2024-02-15T10:30:00Z"
    }
  ]
}
```

---

### POST `/partner/withdraw`

Request withdrawal.

**Request:**
```json
{
  "amount": 5000,
  "method": "bank_transfer",
  "requisites": "Account number details"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "amount": 5000,
  "status": "PENDING",
  "method": "bank_transfer",
  "requisites": "Account number details",
  "created_at": "2024-02-18T10:30:00Z"
}
```

**Errors:**
- `400` - Insufficient balance or below minimum
- `404` - Not a partner

---

### GET `/partner/withdrawals`

List withdrawal requests.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "amount": 5000,
    "status": "PENDING",
    "method": "bank_transfer",
    "requisites": "Account number details",
    "admin_comment": null,
    "created_at": "2024-02-18T10:30:00Z",
    "updated_at": "2024-02-18T10:30:00Z"
  }
]
```

---

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `FORBIDDEN` | 403 | User doesn't have permission |
| `NOT_FOUND` | 404 | Resource not found |
| `BAD_REQUEST` | 400 | Invalid request data |
| `CONFLICT` | 409 | Resource conflict (e.g., already exists) |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/auth/telegram` | 5 requests/minute |
| All other endpoints | 60 requests/minute |
| File uploads | 10 requests/minute |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1708272060
```

---

## Pagination

### Query Parameters

| Parameter | Default | Max |
|-----------|---------|-----|
| `page` | 1 | - |
| `limit` | 20 | 100 |

### Response Format

```json
{
  "data": [],
  "pagination": {
    "total": 100,
    "page": 1,
    "limit": 20,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## Authentication

### JWT Token Format

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "user_id": 123456789,
  "exp": 1708876800,
  "type": "access"
}
```

### Token Usage

Include in Authorization header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## WebSocket (Future)

For real-time notifications (not implemented in v1).

```
wss://bot.domain.com/ws
```

**Messages:**
- `notification` - New notification
- `payment_status` - Payment status update
- `subscription_status` - Subscription status change
