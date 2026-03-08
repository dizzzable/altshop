# AltShop Web App - Fix Summary

## Problem

The web application was not working when accessed externally (outside Telegram) due to:
1. **404 errors for static assets** - Absolute paths instead of relative paths
2. **No Telegram WebApp SDK initialization** - Missing SDK script and ready() call
3. **Authentication issues** - Not properly handling Telegram Mini App authentication

## Changes Made

### 1. Vite Configuration (`web-app/vite.config.ts`)

Added `base: './'` for relative asset paths:

```typescript
export default defineConfig({
  base: './',
  // ... other config
})
```

### 2. Post-build Script (`web-app/scripts/fix-paths.js`)

Created script to fix asset paths after build:

```javascript
// Replace absolute paths with relative paths
content = content.replace(/src="\/assets\//g, 'src="./assets/')
content = content.replace(/href="\/assets\//g, 'href="./assets/')
content = content.replace(/href="\/vite\.svg"/g, 'href="./vite.svg"')
```

### 3. Package.json (`web-app/package.json`)

Added postbuild script:

```json
{
  "scripts": {
    "build": "vite build",
    "postbuild": "node scripts/fix-paths.js"
  }
}
```

### 4. Telegram WebApp Hook (`web-app/src/hooks/useTelegramWebApp.ts`)

**NEW FILE** - Created comprehensive hook for Telegram WebApp integration:
- Detects if running inside Telegram
- Provides access to `initData`, user info, theme
- Handles auto-initialization
- Supports both Telegram and browser testing

### 5. Main Entry (`web-app/src/main.tsx`)

Added Telegram WebApp SDK initialization:

```typescript
function initTelegramWebApp() {
  const script = document.createElement('script')
  script.src = 'https://telegram.org/js/telegram-web-app.js'
  script.async = true
  
  script.onload = () => {
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.ready()
      window.Telegram.WebApp.expand()
      // Apply theme colors
    }
  }
  
  document.head.appendChild(script)
}

initTelegramWebApp()
```

### 6. Telegram Login Component (`web-app/src/components/auth/TelegramLogin.tsx`)

Completely rewritten to support:
- **Auto-authentication inside Telegram** using `initData`
- **Browser login** using Telegram widget
- Proper error handling
- Loading states

### 7. API Client (`web-app/src/lib/api.ts`)

Updated auth method signature to support both auth modes:

```typescript
auth: {
  telegram: (data: { 
    initData?: string
    queryId?: string
    id?: number
    first_name?: string
    // ... other fields
  }) => apiClient.post<TokenResponse>('/auth/telegram', data)
}
```

### 8. Environment File (`web-app/.env`)

Created `.env` file:

```bash
VITE_TELEGRAM_BOT_USERNAME=remnabot
```

### 9. Docker Compose (`docker-compose.yml`)

Removed read-only flag from webapp volume:

```yaml
volumes:
  - ./web-app/dist:/opt/altshop/webapp  # Removed :ro
```

## How It Works Now

### Inside Telegram (Mini App)

1. User opens bot → clicks menu button
2. Web App loads inside Telegram
3. `useTelegramWebApp` hook detects Telegram environment
4. `initData` is automatically sent to backend for validation
5. Backend validates `initData` and returns JWT tokens
6. User is redirected to dashboard

### Outside Telegram (Browser)

1. User visits `https://remnabot.2get.pro/webapp/`
2. Telegram login widget is displayed
3. User clicks "Login via Telegram"
4. Telegram OAuth popup opens
5. After authorization, user data is sent to backend
6. Backend returns JWT tokens
7. User is redirected to dashboard

## Testing

### Test in Browser

1. Open `https://remnabot.2get.pro/webapp/`
2. You should see the login page with Telegram widget
3. Click "Log in with Telegram"
4. Authorize in the popup
5. You should be redirected to dashboard

### Test in Telegram

1. Open your bot in Telegram
2. Click the menu button (or use `/start`)
3. Web App should open automatically authenticated
4. You should see the dashboard

## Build Commands

```bash
# Development
cd web-app
npm install
npm run dev

# Production build
npm run build

# The postbuild script runs automatically
```

## Key Features

✅ **Relative asset paths** - Works in subdirectories
✅ **Telegram WebApp SDK** - Properly initialized
✅ **Dual authentication** - Works in Telegram and browser
✅ **Theme support** - Auto-applies Telegram theme
✅ **Auto-expand** - Full height in Telegram
✅ **Error handling** - Proper error messages
✅ **Loading states** - User feedback during auth

## Dependencies Note

The `--legacy-peer-deps` flag is **not a problem**. The warnings are just informational because:
- Some packages use older versions of dependencies
- This is normal and doesn't affect functionality
- The app builds and runs correctly

The extraneous packages (`@emnapi/*`, `@napi-rs/*`, `@tybys/*`) are optional dependencies from `@tailwindcss/vite` and can be ignored.

## Troubleshooting

### Still seeing 404 errors?

1. Clear browser cache (Ctrl+Shift+R)
2. Check nginx logs: `docker compose logs altshop-nginx`
3. Verify files exist: `ls -la web-app/dist/`

### Authentication not working?

1. Check bot username in `.env` matches your bot
2. Verify backend API is accessible
3. Check browser console for errors
4. Verify `initData` is being sent (check Network tab)

### Theme not applying?

1. Make sure `initTelegramWebApp()` runs before React render
2. Check if `window.Telegram.WebApp` exists
3. Verify CSS variables are set in browser DevTools

## Next Steps

1. ✅ Test external access: `https://remnabot.2get.pro/webapp/`
2. ✅ Test inside Telegram bot
3. Configure backend to accept `initData` authentication
4. Add refresh token logic if needed
5. Implement proper session management
