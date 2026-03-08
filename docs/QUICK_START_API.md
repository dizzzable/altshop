# Quick Start: Using the New Parity API

## For Backend Developers

### Adding a New Endpoint

1. **Add to `src/api/endpoints/user.py`:**

```python
@router.get("/your-endpoint", response_model=YourResponseModel)
@inject
async def your_endpoint(
    current_user: UserDto = Depends(get_current_user),
    your_service: FromDishka[YourService] = None,
) -> YourResponseModel:
    """Your endpoint description."""
    # Your logic here
    return YourResponseModel(...)
```

2. **Add request/response models** at the top of the file with other models

3. **Inject the router** in `src/api/app.py` (already done for `user_router`)

### Service Integration Example

```python
@router.post("/subscription/purchase", response_model=PurchaseResponse)
@inject
async def purchase_subscription(
    request: PurchaseRequest,
    current_user: UserDto = Depends(get_current_user),
    subscription_service: FromDishka[SubscriptionService] = None,
    transaction_service: FromDishka[TransactionService] = None,
) -> PurchaseResponse:
    # Get the plan
    plan = await subscription_service.get_plan(request.plan_id)
    
    # Create transaction
    transaction = await transaction_service.create(
        user=current_user,
        plan=plan,
        purchase_type=request.purchase_type,
        # ...
    )
    
    # Get payment URL
    payment_url = await transaction_service.get_payment_url(transaction)
    
    return PurchaseResponse(
        transaction_id=transaction.payment_id,
        payment_url=payment_url,
        status="PENDING",
        message="Payment initiated",
    )
```

### Error Handling

```python
from fastapi import HTTPException, status

# Resource not found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Subscription not found",
)

# Access denied
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Access denied to this subscription",
)

# Validation error
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Device limit reached",
)
```

---

## For Frontend Developers

### Using the API Client

```typescript
import { api } from '@/lib/api'

// Get subscriptions
const { data: subscriptions } = useQuery({
  queryKey: ['subscriptions'],
  queryFn: () => api.subscription.list().then(r => r.data),
})

// Generate device link
const generateMutation = useMutation({
  mutationFn: (data) => api.devices.generate(data),
  onSuccess: (data) => {
    console.log('Generated:', data.data.connection_url)
  },
  onError: (error) => {
    toast.error(error.response?.data?.detail)
  },
})
```

### Adding New API Methods

Edit `web-app/src/lib/api.ts`:

```typescript
export const api = {
  // Add your new method
  yourModule: {
    yourMethod: (param: string) => 
      apiClient.get<YourType>(`/api/v1/your-endpoint/${param}`),
  },
}
```

### Type Safety

All types are in `web-app/src/types/index.ts`:

```typescript
import type { 
  Subscription, 
  Device, 
  PromocodeActivateResult,
  PartnerInfo 
} from '@/types'
```

---

## Testing Locally

### Backend

```bash
# Start the development server
cd D:\altshop-0.9.3
uv run python -m src

# Test an endpoint
curl -X GET http://localhost:5000/api/v1/user/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Frontend

```bash
# Start dev server
cd D:\altshop-0.9.3\web-app
npm run dev

# Build for production
npm run build
```

---

## Common Patterns

### Pagination

```typescript
// Backend
@router.get("/items", response_model=ItemListResponse)
async list_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    # ...
):
    items = await service.get_all(page=page, limit=limit)
    return ItemListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )

// Frontend
const { data } = useQuery({
  queryKey: ['items', page, limit],
  queryFn: () => api.items.list(page, limit),
})
```

### Mutations with Confirmation

```typescript
// Backend with branching response
@router.post("/promocode/activate")
async activate_promocode(request: PromocodeActivateRequest):
    # Check if subscription selection needed
    if needs_selection:
        return PromocodeActivateResponse(
            message="Select subscription",
            next_step="SELECT_SUBSCRIPTION",
            available_subscriptions=[1, 2, 3],
        )
    
    # Direct success
    return PromocodeActivateResponse(
        message="Success!",
        reward={...},
        next_step=None,
    )

// Frontend handling
const mutation = useMutation({
  mutationFn: (data) => api.promocode.activate(data),
  onSuccess: (result) => {
    if (result.data.next_step === 'SELECT_SUBSCRIPTION') {
      // Show selection dialog
      openSelectionDialog(result.data)
    } else {
      // Success
      toast.success(result.data.message)
    }
  },
})
```

---

## Debugging

### Backend Logs

Check `logs/` directory for API request logs.

### Frontend Console

```typescript
// Enable API debugging
apiClient.interceptors.request.use((config) => {
  console.log('Request:', config)
  return config
})

apiClient.interceptors.response.use((response) => {
  console.log('Response:', response)
  return response
})
```

### Common Issues

**401 Unauthorized:**
- Check if token is in localStorage
- Verify token hasn't expired
- Check refresh token logic

**403 Forbidden:**
- User doesn't own the resource
- Insufficient permissions

**404 Not Found:**
- Resource doesn't exist
- Wrong ID format

**CORS Errors:**
- Check nginx configuration
- Verify backend CORS settings

---

## API Versioning

Current version: **v1** (`/api/v1/*`)

When breaking changes are needed:
1. Create `/api/v2/*` endpoints
2. Deprecate v1 with `X-Deprecation-Warning` header
3. Provide 30-day migration period
4. Update frontend to v2
5. Remove v1

---

## Security Notes

### Authentication

All user endpoints require `Authorization: Bearer {token}` header.

Exception: Public endpoints like `/api/v1/auth/login`, `/api/v1/auth/register`

### Authorization

Always check resource ownership:

```python
subscription = await subscription_service.get(subscription_id)
if subscription.user_telegram_id != current_user.telegram_id:
    raise HTTPException(status_code=403, detail="Access denied")
```

### Rate Limiting

Implement rate limiting for:
- Auth endpoints: 10/min
- Purchase: 30/min
- Device generation: 10/min

---

## Resources

- **API Contract:** `docs/API_CONTRACT.md`
- **Implementation Summary:** `docs/BOT_WEB_PARITY_IMPLEMENTATION.md`
- **Backend Code:** `src/api/endpoints/user.py`
- **Frontend Client:** `web-app/src/lib/api.ts`
- **TypeScript Types:** `web-app/src/types/index.ts`

---

**Need Help?** Check the comprehensive documentation or ask the team!
