# OpenAPI Schema Generation & TypeScript Client Setup

**Version:** 1.0  
**Date:** 2026-02-20  
**Purpose:** Auto-generate TypeScript types and API client from FastAPI OpenAPI schema

---

## Overview

This guide shows how to automatically generate TypeScript types and a type-safe API client from your FastAPI backend's OpenAPI schema.

### Benefits

- ✅ **Type Safety** - Autocomplete for methods, requests, and responses
- ✅ **Auto-Sync** - Types update when backend changes
- ✅ **Early Errors** - Catch API mismatches at compile time
- ✅ **Less Code** - No manual type definitions needed
- ✅ **Documentation** - OpenAPI docs always up-to-date

---

## Setup Guide

### Option 1: Hey API (Recommended) ⭐

**Best for:** Modern TypeScript projects with FastAPI

#### Step 1: Install Package

```bash
cd web-app
npm install --save-dev @hey-api/openapi-ts
```

#### Step 2: Add Generation Script

Add to `web-app/package.json`:

```json
{
  "scripts": {
    "generate:api": "openapi-ts -i http://localhost:5000/openapi.json -o src/generated --client axios"
  }
}
```

#### Step 3: Generate Client

```bash
# Start backend first
cd D:\\altshop-0.9.3
uv run python -m src

# In another terminal, generate client
cd web-app
npm run generate:api
```

#### Step 4: Use Generated Client

```typescript
import { SubscriptionService, DevicesService } from './src/generated'

// Type-safe API calls
const subscriptions = await SubscriptionService.subscriptionList()
const devices = await DevicesService.devicesList({ subscriptionId: 1 })

// Full type safety
const sub: SubscriptionResponse = subscriptions[0]
```

---

### Option 2: OpenAPI TypeScript Codegen

**Best for:** Projects needing axios client

#### Step 1: Install Package

```bash
cd web-app
npm install --save-dev openapi-typescript-codegen
```

#### Step 2: Add Script

```json
{
  "scripts": {
    "generate:api": "openapi-typescript-codegen --input http://localhost:5000/openapi.json --output src/generated --client axios"
  }
}
```

#### Step 3: Generate

```bash
npm run generate:api
```

---

### Option 3: OpenAPI Typescript (Types Only)

**Best for:** Projects with custom API client

#### Step 1: Install Package

```bash
cd web-app
npm install --save-dev openapi-typescript
```

#### Step 2: Add Script

```json
{
  "scripts": {
    "generate:types": "npx openapi-typescript http://localhost:5000/openapi.json --output src/generated/types.ts"
  }
}
```

#### Step 3: Generate

```bash
npm run generate:types
```

---

## Enhanced Setup with Preprocessing

For cleaner method names and better organization:

### Step 1: Download OpenAPI Schema

```bash
# Create script: scripts/download-openapi.sh
curl http://localhost:5000/openapi.json -o openapi.json
```

### Step 2: Preprocess OpenAPI (Optional)

Create `scripts/preprocess-openapi.js`:

```javascript
import * as fs from 'fs'

async function modifyOpenAPIFile(filePath) {
  const data = await fs.promises.readFile(filePath)
  const openapiContent = JSON.parse(data)

  // Clean up operation IDs for better method names
  for (const pathKey of Object.keys(openapiContent.paths)) {
    const pathData = openapiContent.paths[pathKey]
    for (const method of Object.keys(pathData)) {
      const operation = pathData[method]
      if (operation.tags && operation.tags.length > 0) {
        const tag = operation.tags[0]
        const operationId = operation.operationId
        const toRemove = `${tag}-`
        if (operationId.startsWith(toRemove)) {
          operation.operationId = operationId.substring(toRemove.length)
        }
      }
    }
  }

  await fs.promises.writeFile(filePath, JSON.stringify(openapiContent, null, 2))
}

modifyOpenAPIFile('./openapi.json')
```

### Step 3: Generate from Preprocessed Spec

```bash
# Download
curl http://localhost:5000/openapi.json -o openapi.json

# Preprocess
node scripts/preprocess-openapi.js

# Generate
npm run generate:api
```

---

## FastAPI Configuration

### Add Custom Operation IDs

In `src/api/app.py`:

```python
def custom_generate_unique_id(route: APIRoute):
    """Generate cleaner operation IDs for client generation."""
    # Format: {tag}_{method}
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}_{route.name}"

app = FastAPI(
    title="AltShop API",
    description="Bot ↔ Web Parity API",
    version="1.0.0",
    generate_unique_id_function=custom_generate_unique_id,
)
```

### Add Tags to Routes

In `src/api/endpoints/user.py`:

```python
router = APIRouter(
    prefix="/api/v1",
    tags=["User API"]  # This becomes the service name
)

# Each endpoint automatically gets tagged
@router.get("/user/me", tags=["Users"])
async def get_user_profile(...):
    ...

@router.get("/subscription/list", tags=["Subscriptions"])
async def list_subscriptions(...):
    ...
```

---

## Generated Structure

### Hey API Output

```
src/generated/
├── core/
│   ├── ApiError.ts
│   ├── ApiRequest.ts
│   ├── ApiResult.ts
│   └── request.ts
├── services/
│   ├── UsersService.ts
│   ├── SubscriptionsService.ts
│   ├── DevicesService.ts
│   ├── PromocodesService.ts
│   ├── ReferralsService.ts
│   └── PartnerService.ts
├── types.ts
└── index.ts
```

### Usage Example

```typescript
import { 
  UsersService,
  SubscriptionsService,
  DevicesService,
  type SubscriptionResponse,
  type DeviceResponse
} from './src/generated'

// Get user profile
const user = await UsersService.getUserMe()
console.log(user.username) // Type-safe!

// List subscriptions
const subs = await SubscriptionsService.subscriptionList()
const firstSub: SubscriptionResponse = subs[0]

// Generate device link
const device = await DevicesService.devicesGenerate({
  subscriptionId: 1,
  deviceType: 'ANDROID'
})
console.log(device.connectionUrl)

// All with full type safety and autocomplete!
```

---

## Automated Generation Script

Create `scripts/generate-api.sh`:

```bash
#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 API Client Generator"
echo "======================"

# Check if backend is running
echo "📡 Checking backend..."
if ! curl -s http://localhost:5000/openapi.json > /dev/null; then
    echo -e "${RED}❌ Backend is not running!${NC}"
    echo "Start it with: uv run python -m src"
    exit 1
fi

echo -e "${GREEN}✅ Backend is running${NC}"

# Download OpenAPI schema
echo "📥 Downloading OpenAPI schema..."
curl -s http://localhost:5000/openapi.json -o openapi.json

if [ ! -f openapi.json ]; then
    echo -e "${RED}❌ Failed to download OpenAPI schema${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Schema downloaded${NC}"

# Preprocess (optional)
if [ -f scripts/preprocess-openapi.js ]; then
    echo "🔧 Preprocessing schema..."
    node scripts/preprocess-openapi.js
    echo -e "${GREEN}✅ Schema preprocessed${NC}"
fi

# Generate client
echo "🔨 Generating TypeScript client..."
npm run generate:api

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Client generated successfully!${NC}"
    echo ""
    echo "📦 Generated files:"
    ls -la src/generated/
    echo ""
    echo "✨ Usage example:"
    echo "   import { UsersService } from './src/generated'"
    echo "   const user = await UsersService.getUserMe()"
else
    echo -e "${RED}❌ Generation failed${NC}"
    exit 1
fi
```

Make it executable:

```bash
chmod +x scripts/generate-api.sh
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/generate-api.yml`:

```yaml
name: Generate API Client

on:
  push:
    branches: [main]
    paths:
      - 'src/api/**'

jobs:
  generate:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install backend dependencies
        run: |
          pip install uv
          uv sync
      
      - name: Start backend
        run: |
          uv run python -m src &
          sleep 5
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install frontend dependencies
        run: cd web-app && npm ci
      
      - name: Generate API client
        run: cd web-app && ./scripts/generate-api.sh
      
      - name: Commit generated files
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add web-app/src/generated
          git diff --staged --exit-code || git commit -m "Auto-generate API client"
          git push
```

---

## Migration from Manual Types

### Current Manual Types

```typescript
// web-app/src/types/index.ts
export interface Subscription {
  id: number
  status: string
  // ...
}
```

### Generated Types

```typescript
// web-app/src/generated/types.ts
export interface SubscriptionResponse {
  id: number
  status: string
  // ... automatically from Pydantic!
}
```

### Migration Steps

1. **Generate client**
   ```bash
   npm run generate:api
   ```

2. **Update imports**
   ```typescript
   // Before
   import type { Subscription } from '@/types'
   
   // After
   import type { SubscriptionResponse } from '@/generated'
   ```

3. **Keep manual types for frontend-only types**
   ```typescript
   // Keep in @/types for UI-specific types
   export interface DashboardStats {
     // Frontend-only computed values
   }
   ```

4. **Update API client**
   ```typescript
   // Before
   export const api = {
     subscription: {
       list: () => apiClient.get<Subscription[]>('/api/v1/subscription/list'),
     },
   }
   
   // After - use generated client
   import { SubscriptionsService } from '@/generated'
   // api.subscription.list() → SubscriptionsService.subscriptionList()
   ```

---

## Troubleshooting

### Issue: Operation ID Conflicts

**Error:** `Duplicate operationId found`

**Solution:**
```python
# Add custom unique ID function
def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0]}_{route.name}"

app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

### Issue: Missing Types

**Problem:** Some types not generated

**Solution:**
- Ensure all response models use Pydantic
- Add `response_model` to all endpoints
- Check OpenAPI schema at `/openapi.json`

### Issue: Circular Dependencies

**Problem:** TypeScript circular reference errors

**Solution:**
```typescript
// Generated code handles this automatically
// If manual fixes needed, use forward references
export interface User {
  subscriptions?: Subscription[]
}

export interface Subscription {
  user?: User  // OK with generated code
}
```

---

## Best Practices

### 1. Generate on Backend Changes

```bash
# Add to backend dev workflow
uv run python -m src  # Terminal 1
npm run generate:api  # Terminal 2 (watch mode)
```

### 2. Version Control

```gitignore
# .gitignore
src/generated/  # Generated code
openapi.json    # Schema (optional)
```

OR commit generated files for CI/CD consistency.

### 3. Type Extensions

```typescript
// Extend generated types if needed
import { SubscriptionResponse } from './generated'

export interface SubscriptionWithUI extends SubscriptionResponse {
  // Add UI-specific computed fields
  isActive: boolean
  daysRemaining: number
}
```

### 4. Error Handling

```typescript
import { ApiError } from './generated'

try {
  const user = await UsersService.getUserMe()
} catch (error) {
  if (error instanceof ApiError) {
    console.error('API Error:', error.body)
  }
}
```

---

## Next Steps

1. ✅ **Install Hey API** - `npm install --save-dev @hey-api/openapi-ts`
2. ✅ **Add generation script** - Update `package.json`
3. ✅ **Test generation** - Run `npm run generate:api`
4. ✅ **Update imports** - Migrate to generated types
5. ✅ **Add to CI/CD** - Auto-generate on backend changes

---

**Tools Compared:**

| Tool | Types | Client | FastAPI Support | Ease |
|------|-------|--------|-----------------|------|
| **Hey API** | ✅ | ✅ | ⭐⭐⭐⭐⭐ | Easy |
| **OpenAPI TS Codegen** | ✅ | ✅ | ⭐⭐⭐⭐ | Medium |
| **OpenAPI Typescript** | ✅ | ❌ | ⭐⭐⭐⭐⭐ | Easy |
| **Orval** | ✅ | ✅ | ⭐⭐⭐ | Medium |

**Recommendation:** Use **Hey API** for best FastAPI integration ⭐

---

**Last Updated:** 2026-02-20  
**Status:** Ready to implement
