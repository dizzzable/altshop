# Service Integration Implementation Guide

**Version:** 1.0  
**Date:** 2026-02-20  
**Purpose:** Connect API endpoints to existing business logic

---

## Overview

This document provides step-by-step implementation patterns for connecting the new REST API endpoints to existing bot services.

### Architecture Principle

**API Layer = Adapter Pattern**
- API endpoints should be thin adapters
- Business logic stays in `src/services/*`
- Reuse existing Taskiq tasks where possible
- Maintain backward compatibility with bot flows

---

## 1. Subscription Purchase Integration

### Current Bot Flow

```
User selects plan → Duration → Device → Payment → 
Create Transaction → Get Payment URL → 
User pays → Webhook → purchase_subscription_task → 
Create Remnawave user → Create subscription
```

### API Integration Pattern

```python
@router.post("/subscription/purchase", response_model=PurchaseResponse)
@inject
async def purchase_subscription(
    request: PurchaseRequest,
    current_user: UserDto = Depends(get_current_user),
    payment_gateway_service: FromDishka[PaymentGatewayService] = None,
    plan_service: FromDishka[PlanService] = None,
    pricing_service: FromDishka[PricingService] = None,
    transaction_service: FromDishka[TransactionService] = None,
) -> PurchaseResponse:
    """
    Purchase subscription via API.
    
    This endpoint:
    1. Validates plan and duration
    2. Calculates price with discounts
    3. Creates transaction
    4. Gets payment URL from gateway
    5. Returns payment URL for frontend
    """
    # 1. Get plan
    plan = await plan_service.get(request.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    
    # 2. Get duration
    duration = next(
        (d for d in plan.durations if d.days == request.duration_days),
        None
    )
    if not duration:
        raise HTTPException(400, "Invalid duration")
    
    # 3. Get price for gateway
    gateway_type = request.gateway_type or "TELEGRAM_STARS"
    price_obj = next(
        (p for p in duration.prices if p.gateway_type == gateway_type),
        None
    )
    if not price_obj:
        raise HTTPException(400, "Price not found for gateway")
    
    # 4. Calculate final price with discounts
    from decimal import Decimal
    final_price = pricing_service.calculate(
        user=current_user,
        price=Decimal(price_obj.price),
        currency=price_obj.currency
    )
    
    # 5. Create transaction
    from src.core.enums import TransactionStatus, PurchaseType
    from src.infrastructure.database.models.dto import PlanSnapshotDto, TransactionDto
    from uuid import uuid4
    
    transaction_dto = TransactionDto(
        payment_id=uuid4(),
        user_telegram_id=current_user.telegram_id,
        status=TransactionStatus.PENDING,
        purchase_type=request.purchase_type or PurchaseType.NEW,
        gateway_type=gateway_type,
        pricing=final_price,
        currency=price_obj.currency,
        plan=PlanSnapshotDto.from_plan(plan),  # Convert Plan to PlanSnapshot
        renew_subscription_id=request.renew_subscription_id,
        device_types=request.device_types,
        is_test=False,
    )
    
    transaction = await transaction_service.create(current_user, transaction_dto)
    
    # 6. Get payment URL from gateway
    gateway_service = await payment_gateway_service.get_by_type(gateway_type)
    if not gateway_service:
        raise HTTPException(400, f"Gateway {gateway_type} not available")
    
    payment_gateway: BasePaymentGateway = payment_gateway_factory.get(gateway_type)
    payment_result = await payment_gateway.create_payment(
        transaction=transaction,
        user=current_user
    )
    
    # 7. Return payment URL
    return PurchaseResponse(
        transaction_id=str(transaction.payment_id),
        payment_url=payment_result.url,
        status="PENDING",
        message="Payment initiated"
    )
```

### Webhook Handling

The existing webhook already handles payment completion via `purchase_subscription_task`. No changes needed!

---

## 2. Device Management Integration

### Generate Device Link

```python
@router.post("/devices/generate", response_model=GenerateDeviceResponse)
@inject
async def generate_device_link(
    request: GenerateDeviceRequest,
    current_user: UserDto = Depends(get_current_user),
    subscription_service: FromDishka[SubscriptionService] = None,
    remnawave_service: FromDishka[RemnawaveService] = None,
) -> GenerateDeviceResponse:
    """Generate new device connection link."""
    
    # 1. Get and validate subscription
    subscription = await subscription_service.get(request.subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")
    
    if subscription.user_telegram_id != current_user.telegram_id:
        raise HTTPException(403, "Access denied")
    
    # 2. Check device limit
    if subscription.devices_count >= subscription.device_limit:
        raise HTTPException(
            400, 
            f"Device limit reached: {subscription.devices_count}/{subscription.device_limit}"
        )
    
    # 3. Generate device link via Remnawave
    device_type = request.device_type or DeviceType.ANDROID
    
    # Use existing RemnawaveService method
    device_info = await remnawave_service.generate_device_key(
        user_remna_id=subscription.user_remna_id,
        device_type=device_type
    )
    
    # 4. Return connection URL
    return GenerateDeviceResponse(
        hwid=device_info.hwid,
        connection_url=device_info.connection_url,
        device_type=device_type
    )
```

### Revoke Device

```python
@router.delete("/devices/{hwid}")
@inject
async def revoke_device(
    hwid: str,
    subscription_id: int = Query(...),
    current_user: UserDto = Depends(get_current_user),
    subscription_service: FromDishka[SubscriptionService] = None,
    remnawave_service: FromDishka[RemnawaveService] = None,
) -> dict:
    """Revoke device access."""
    
    # 1. Validate subscription ownership
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")
    
    if subscription.user_telegram_id != current_user.telegram_id:
        raise HTTPException(403, "Access denied")
    
    # 2. Revoke in Remnawave
    success = await remnawave_service.revoke_device(
        user_remna_id=subscription.user_remna_id,
        hwid=hwid
    )
    
    if not success:
        raise HTTPException(400, "Failed to revoke device")
    
    return {"success": True, "message": f"Device {hwid} revoked"}
```

---

## 3. Promocode Activation Integration

### With Branching Logic

```python
@router.post("/promocode/activate", response_model=PromocodeActivateResponse)
@inject
async def activate_promocode(
    request: PromocodeActivateRequest,
    current_user: UserDto = Depends(get_current_user),
    promocode_service: FromDishka[PromocodeService] = None,
    subscription_service: FromDishka[SubscriptionService] = None,
) -> PromocodeActivateResponse:
    """
    Activate promocode with branching flow.
    
    Branching logic:
    1. If promocode gives days/traffic/devices → apply to subscription
    2. If multiple subscriptions exist → ask user to select
    3. If promocode creates new subscription → confirm creation
    """
    
    # 1. Get promocode
    promocode = await promocode_service.get_by_code(request.code)
    if not promocode:
        raise HTTPException(400, "Invalid promocode")
    
    # 2. Check if already activated
    already_activated = await promocode_service.is_activated_by_user(
        promocode.id, 
        current_user.telegram_id
    )
    if already_activated:
        raise HTTPException(400, "Promocode already used")
    
    # 3. Determine reward type and branching
    reward_type = promocode.reward_type
    
    if reward_type == PromocodeRewardType.SUBSCRIPTION:
        # Create new subscription flow
        return PromocodeActivateResponse(
            message="This promocode creates a new subscription",
            reward={
                "type": "SUBSCRIPTION",
                "value": promocode.reward_value
            },
            next_step="CREATE_NEW"
        )
    
    elif reward_type in [
        PromocodeRewardType.DURATION,
        PromocodeRewardType.TRAFFIC,
        PromocodeRewardType.DEVICES
    ]:
        # Need to select subscription
        subscriptions = await subscription_service.get_all_by_user(
            current_user.telegram_id
        )
        active_subs = [s for s in subscriptions if s.status == "ACTIVE"]
        
        if len(active_subs) == 0:
            raise HTTPException(400, "No active subscriptions to apply reward")
        
        elif len(active_subs) == 1:
            # Auto-apply to single subscription
            await promocode_service.activate_on_subscription(
                promocode_id=promocode.id,
                user=current_user,
                subscription=active_subs[0]
            )
            
            return PromocodeActivateResponse(
                message=f"Added {promocode.reward_value} {reward_type.value} to subscription",
                reward={
                    "type": reward_type.value,
                    "value": promocode.reward_value
                },
                next_step=None
            )
        
        else:
            # Multiple subscriptions - ask to select
            return PromocodeActivateResponse(
                message="Select subscription to add reward",
                reward={
                    "type": reward_type.value,
                    "value": promocode.reward_value
                },
                next_step="SELECT_SUBSCRIPTION",
                available_subscriptions=[s.id for s in active_subs]
            )
    
    elif reward_type in [
        PromocodeRewardType.PERSONAL_DISCOUNT,
        PromocodeRewardType.PURCHASE_DISCOUNT
    ]:
        # Apply discount to user profile
        await promocode_service.activate_discount(
            promocode_id=promocode.id,
            user=current_user
        )
        
        return PromocodeActivateResponse(
            message=f"Discount {promocode.reward_value}% activated",
            reward={
                "type": reward_type.value,
                "value": promocode.reward_value
            },
            next_step=None
        )
    
    # Fallback
    raise HTTPException(400, "Unknown promocode type")
```

---

## 4. Referral Info Integration

```python
@router.get("/referral/info", response_model=ReferralInfoResponse)
@inject
async def get_referral_info(
    current_user: UserDto = Depends(get_current_user),
    referral_service: FromDishka[ReferralService] = None,
) -> ReferralInfoResponse:
    """Get user's referral information."""
    
    # Use existing ReferralService methods
    referral_count = await referral_service.get_referral_count(current_user.telegram_id)
    reward_count = await referral_service.get_reward_count(current_user.telegram_id)
    points = await referral_service.get_user_points(current_user.telegram_id)
    
    # Generate referral link
    from src.core.constants import REFERRAL_PREFIX, T_ME
    bot_username = await referral_service.get_bot_username()  # Cache this
    
    referral_code = f"{REFERRAL_PREFIX}{current_user.telegram_id}"
    referral_link = f"{T_ME}{bot_username}?start={referral_code}"
    
    return ReferralInfoResponse(
        referral_count=referral_count,
        reward_count=reward_count,
        referral_link=referral_link,
        referral_code=referral_code,
        points=points
    )
```

---

## 5. Partner Operations Integration

### Get Partner Info

```python
@router.get("/partner/info", response_model=PartnerInfoResponse)
@inject
async def get_partner_info(
    current_user: UserDto = Depends(get_current_user),
    partner_service: FromDishka[PartnerService] = None,
) -> PartnerInfoResponse:
    """Get partner information."""
    
    partner = await partner_service.get_partner_by_user(current_user.telegram_id)
    
    if not partner:
        # Check if user qualifies for partner program
        referral_count = await partner_service.get_referral_count(current_user.telegram_id)
        
        if referral_count < 3:  # Example threshold
            return PartnerInfoResponse(
                is_partner=False,
                balance=0,
                total_earned=0,
                total_withdrawn=0,
                referrals_count=referral_count,
                level2_referrals_count=0,
                level3_referrals_count=0
            )
        
        # Auto-enroll in partner program
        partner = await partner_service.create_partner(current_user)
    
    return PartnerInfoResponse(
        is_partner=True,
        balance=partner.balance,
        total_earned=partner.total_earned,
        total_withdrawn=partner.total_withdrawn,
        referrals_count=partner.referrals_count,
        level2_referrals_count=partner.level2_referrals_count,
        level3_referrals_count=partner.level3_referrals_count
    )
```

### Request Withdrawal

```python
@router.post("/partner/withdraw", response_model=PartnerWithdrawalResponse)
@inject
async def request_withdrawal(
    request: PartnerWithdrawalRequest,
    current_user: UserDto = Depends(get_current_user),
    partner_service: FromDishka[PartnerService] = None,
) -> PartnerWithdrawalResponse:
    """Request withdrawal from partner balance."""
    
    # 1. Get partner
    partner = await partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner:
        raise HTTPException(403, "Not a partner")
    
    # 2. Validate amount
    min_withdrawal = await partner_service.get_minimum_withdrawal()
    if request.amount < min_withdrawal:
        raise HTTPException(400, f"Minimum withdrawal is {min_withdrawal}")
    
    if request.amount > partner.balance:
        raise HTTPException(400, "Insufficient balance")
    
    # 3. Create withdrawal request
    from src.core.enums import WithdrawalStatus
    from src.infrastructure.database.models.dto import PartnerWithdrawalDto
    
    withdrawal_dto = PartnerWithdrawalDto(
        partner_id=partner.id,
        amount=request.amount,
        status=WithdrawalStatus.PENDING,
        method=request.method,
        requisites=request.requisites,
        admin_comment=None
    )
    
    withdrawal = await partner_service.create_withdrawal(withdrawal_dto)
    
    # 4. Notify admins (optional)
    await partner_service.notify_admins_withdrawal_request(withdrawal)
    
    return PartnerWithdrawalResponse(
        id=withdrawal.id,
        amount=withdrawal.amount,
        status=withdrawal.status.value,
        method=withdrawal.method,
        requisites=withdrawal.requisites,
        admin_comment=withdrawal.admin_comment,
        created_at=withdrawal.created_at.isoformat(),
        updated_at=withdrawal.updated_at.isoformat()
    )
```

---

## 6. Error Handling Patterns

### Standard API Errors

```python
from fastapi import HTTPException, status

# Resource not found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Subscription not found"
)

# Access denied (ownership check)
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Access denied to this subscription"
)

# Validation error
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Device limit reached"
)

# Business logic error
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="User already has trial subscription"
)

# Service unavailable
raise HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Payment gateway temporarily unavailable"
)
```

### Consistent Error Response

```python
from pydantic import BaseModel

class ApiError(BaseModel):
    code: str
    message: str
    details: dict | None = None

class ErrorResponse(BaseModel):
    error: ApiError

# Usage in endpoint
@router.post("/endpoint", response_model=SuccessResponse | ErrorResponse)
async def endpoint():
    try:
        # Logic
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e),
                "details": {}
            }
        )
```

---

## 7. Testing Strategy

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_purchase_subscription(
    mock_user_service,
    mock_plan_service,
    mock_transaction_service,
    api_client
):
    # Arrange
    mock_user_service.get.return_value = test_user
    mock_plan_service.get.return_value = test_plan
    
    # Act
    response = await api_client.post(
        "/api/v1/subscription/purchase",
        json={
            "plan_id": 1,
            "duration_days": 30,
            "purchase_type": "NEW"
        }
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["transaction_id"] is not None
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_purchase_flow(
    db_session,
    api_client,
    test_user
):
    # 1. Login
    auth_response = await api_client.post("/api/v1/auth/login", ...)
    token = auth_response.json()["access_token"]
    
    # 2. Purchase subscription
    purchase_response = await api_client.post(
        "/api/v1/subscription/purchase",
        json={...},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 3. Verify transaction created
    transaction_id = purchase_response.json()["transaction_id"]
    db_transaction = await db_session.get(Transaction, transaction_id)
    assert db_transaction is not None
    assert db_transaction.status == "PENDING"
```

---

## 8. Caching Strategy

### User Data Cache

```python
from functools import lru_cache
from datetime import timedelta

@router.get("/user/me")
@inject
async def get_user_profile(
    current_user: UserDto = Depends(get_current_user),
    redis_client: Redis = None,
) -> UserProfileResponse:
    # Check cache
    cache_key = f"user:profile:{current_user.telegram_id}"
    cached = await redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Build response
    response = UserProfileResponse(...)
    
    # Cache for 5 minutes
    await redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(response.dict())
    )
    
    return response
```

### Invalidation

```python
# After user update
await redis_client.delete(f"user:profile:{user.telegram_id}")

# After subscription change
await redis_client.delete(f"subscriptions:{user.telegram_id}")
```

---

## 9. Logging & Monitoring

### Structured Logging

```python
from loguru import logger

@router.post("/subscription/purchase")
async def purchase_subscription(...):
    logger.info(
        "Purchase initiated",
        user_id=current_user.telegram_id,
        plan_id=request.plan_id,
        purchase_type=request.purchase_type
    )
    
    try:
        result = await process_purchase(...)
        
        logger.info(
            "Purchase completed",
            user_id=current_user.telegram_id,
            transaction_id=result.transaction_id
        )
        
        return result
        
    except Exception as e:
        logger.exception(
            "Purchase failed",
            user_id=current_user.telegram_id,
            error=str(e)
        )
        raise
```

### Metrics

```python
from prometheus_client import Counter, Histogram

PURCHASE_COUNTER = Counter(
    "subscription_purchases_total",
    "Total subscription purchases",
    ["status", "gateway_type"]
)

PURCHASE_DURATION = Histogram(
    "purchase_duration_seconds",
    "Time to process purchase"
)

@router.post("/subscription/purchase")
@PURCHASE_DURATION.time()
async def purchase_subscription(...):
    with PURCHASE_DURATION.time():
        result = await process_purchase(...)
    
    PURCHASE_COUNTER.labels(
        status="success",
        gateway_type=request.gateway_type
    ).inc()
    
    return result
```

---

## 10. Security Checklist

- [ ] JWT token validation on all protected endpoints
- [ ] Resource ownership verification
- [ ] Rate limiting on sensitive endpoints
- [ ] Input validation with Pydantic
- [ ] SQL injection prevention (using ORM)
- [ ] XSS prevention (sanitize user input)
- [ ] CSRF protection for state-changing operations
- [ ] Secure password hashing (bcrypt)
- [ ] HTTPS enforcement in production
- [ ] API key rotation for webhooks

---

## Next Steps

1. **Implement purchase endpoint** (highest priority)
2. **Implement device management** (core functionality)
3. **Implement promocode activation** (user experience)
4. **Implement referral/partner endpoints** (engagement)
5. **Add comprehensive tests**
6. **Add monitoring/metrics**
7. **Performance optimization**

---

**Questions?** Check existing bot handlers in `src/bot/routers/` for reference implementations.
