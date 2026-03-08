# Web App Configuration Guide

## Overview

This project includes a web-based user interface (Mini App) that integrates with the Telegram bot. The web app provides a modern, responsive interface for users to manage their VPN subscriptions.

## Environment Variables

All web app configuration is done through the `.env` file. Here are the available settings:

### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `WEB_APP_ENABLED` | Enable/disable the web app | `true` |
| `WEB_APP_URL` | URL where your frontend is hosted | `https://app.yourdomain.com` |
| `WEB_APP_JWT_SECRET` | Secret key for JWT tokens (min 32 chars) | Generate with `openssl rand -base64 32` |
| `WEB_APP_API_SECRET_TOKEN` | API authentication token (min 16 chars) | Generate with `openssl rand -hex 32` |

### Optional Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `WEB_APP_JWT_EXPIRY` | JWT token expiration in seconds | `604800` (7 days) |
| `WEB_APP_JWT_REFRESH_ENABLED` | Enable token refresh endpoint | `true` |
| `WEB_APP_CORS_ORIGINS` | Comma-separated list of allowed origins | Same as `WEB_APP_URL` |
| `WEB_APP_RATE_LIMIT_ENABLED` | Enable rate limiting | `true` |
| `WEB_APP_RATE_LIMIT_MAX_REQUESTS` | Max requests per minute | `60` |
| `WEB_APP_RATE_LIMIT_WINDOW` | Rate limit window in seconds | `60` |

## Quick Start

### 1. Generate Secure Keys

```bash
# Generate JWT secret (min 32 characters)
openssl rand -base64 32

# Generate API secret token (min 16 characters)
openssl rand -hex 32
```

### 2. Update .env File

```env
# Web App Configuration
WEB_APP_ENABLED=true
WEB_APP_URL=https://app.yourdomain.com
WEB_APP_JWT_SECRET=your_generated_jwt_secret_here
WEB_APP_API_SECRET_TOKEN=your_generated_api_token_here
WEB_APP_CORS_ORIGINS=https://app.yourdomain.com
```

### 3. Deploy Frontend

Deploy your React/Vue/Next.js frontend to the specified `WEB_APP_URL`.

### 4. Restart Services

```bash
docker-compose restart altshop
```

## Integration with Telegram Bot

The web app integrates with Telegram through the `BOT_MINI_APP` setting:

```env
# Option 1: Use exact Mini App URL from BotFather
BOT_MINI_APP=https://app.yourdomain.com/webapp/miniapp

# Option 2: Disable Mini App link in bot runtime
BOT_MINI_APP=false
```

## API Endpoints

When the web app is enabled, the following endpoints become available:

- `POST /api/v1/auth/telegram` - Authenticate via Telegram
- `POST /api/v1/auth/refresh` - Refresh JWT token
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/logout` - Logout user

## Security Considerations

1. **Never commit `.env` to version control** - It contains sensitive secrets
2. **Use strong, unique secrets** - Minimum 32 characters for JWT secret
3. **Enable HTTPS** - Always use HTTPS for `WEB_APP_URL`
4. **Configure CORS properly** - Only allow trusted domains
5. **Enable rate limiting** - Protects against DDoS attacks

## Troubleshooting

### Web App Not Loading

1. Check `WEB_APP_URL` is accessible from the internet
2. Verify CORS origins include your frontend domain
3. Check Docker logs: `docker-compose logs altshop`

### JWT Authentication Fails

1. Ensure `WEB_APP_JWT_SECRET` is at least 32 characters
2. Verify the secret matches between backend and frontend
3. Check token expiration time

### CORS Errors

1. Add your frontend domain to `WEB_APP_CORS_ORIGINS`
2. Use comma-separated list for multiple domains
3. Include protocol (https://) in domain names

## Example Frontend Integration

```typescript
// Example React hook for authentication
import { useAuth } from './hooks/useAuth';

function App() {
  const { login, user, logout } = useAuth();
  
  const handleTelegramLogin = async (tgData: TelegramAuthData) => {
    await login(tgData);
  };
  
  return (
    <div>
      {user ? (
        <Dashboard user={user} onLogout={logout} />
      ) : (
        <TelegramLoginButton onData={handleTelegramLogin} />
      )}
    </div>
  );
}
```

## Additional Resources

- [Telegram Web Apps Documentation](https://core.telegram.org/bots/webapps)
- [JWT.io](https://jwt.io/) - JWT decoder and validator
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - API security guide
