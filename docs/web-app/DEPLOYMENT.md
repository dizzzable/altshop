> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - Deployment Guide

## Overview

This guide covers deploying the AltShop Web Application to production.

## Prerequisites

- Node.js 18+ installed on server
- AltShop backend API running and accessible
- Domain name configured
- SSL certificate
- Environment variables configured

## Build Process

### 1. Install Dependencies

```bash
cd web-app
npm install --production
```

### 2. Set Environment Variables

Create `.env.production`:

```bash
VITE_TELEGRAM_BOT_USERNAME=altshop_bot
VITE_API_BASE_URL=https://bot.domain.com/api/v1
```

### 3. Build Application

```bash
npm run build
```

This creates optimized production files in `dist/` directory.

### 4. Verify Build

```bash
npm run preview
```

Check that the application works correctly.

## Server Configuration

### Option 1: Nginx (Recommended)

#### Install Nginx

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

#### Configure Nginx

Create `/etc/nginx/sites-available/altshop-web`:

```nginx
server {
    listen 80;
    server_name bot.domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bot.domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/bot.domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Root directory
    root /var/www/altshop-web/dist;
    index index.html;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # Main location
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API proxy
    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 60s;
    }
    
    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

#### Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/altshop-web /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 2: Docker Deployment

#### Create Dockerfile

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### Create nginx.conf for Docker

```nginx
server {
    listen 80;
    server_name localhost;
    
    root /usr/share/nginx/html;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://host.docker.internal:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Build and Run

```bash
docker build -t altshop-web .
docker run -d -p 80:80 altshop-web
```

### Option 3: Vercel Deployment

#### Install Vercel CLI

```bash
npm install -g vercel
```

#### Deploy

```bash
vercel login
vercel --prod
```

#### Configure Environment Variables

In Vercel dashboard, add:
- `VITE_TELEGRAM_BOT_USERNAME`
- `VITE_API_BASE_URL`

### Option 4: Netlify Deployment

#### Install Netlify CLI

```bash
npm install -g netlify-cli
```

#### Deploy

```bash
netlify login
netlify deploy --prod
```

#### Create netlify.toml

```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "SAMEORIGIN"
    X-Content-Type-Options = "nosniff"
    X-XSS-Protection = "1; mode=block"
```

## SSL Certificate

### Using Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d bot.domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Cron Job for Auto-Renewal

```bash
# Edit crontab
sudo crontab -e

# Add renewal job
0 3 * * * certbot renew --quiet
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_TELEGRAM_BOT_USERNAME` | Telegram bot for login | `altshop_bot` |
| `VITE_API_BASE_URL` | Backend API URL | `https://bot.domain.com/api/v1` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_SENTRY_DSN` | Sentry error tracking | - |
| `VITE_ANALYTICS_ID` | Analytics ID | - |

## Performance Optimization

### 1. Enable Compression

Already configured in Nginx with gzip.

### 2. Browser Caching

Static assets cached for 1 year.

### 3. CDN (Optional)

Configure CDN for static assets:

```javascript
// vite.config.ts
export default {
  build: {
    rollupOptions: {
      output: {
        assetFileNames: 'cdn/static/[name]-[hash][extname]'
      }
    }
  }
}
```

### 4. Lazy Loading

Routes are already lazy loaded with React Router.

## Monitoring

### 1. Application Logs

```bash
# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 2. Uptime Monitoring

Use services like:
- UptimeRobot
- Pingdom
- StatusCake

### 3. Error Tracking

Integrate Sentry:

```bash
npm install @sentry/react
```

```typescript
// src/main.tsx
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: "production",
});
```

## Backup Strategy

### 1. Backup Build Files

```bash
# Create backup directory
mkdir -p /backups/altshop-web

# Backup current build
cp -r /var/www/altshop-web/dist /backups/altshop-web/dist-$(date +%Y%m%d)
```

### 2. Backup Configuration

```bash
# Backup Nginx config
cp /etc/nginx/sites-available/altshop-web /backups/nginx-config-$(date +%Y%m%d)
```

## Rollback Procedure

### 1. Revert to Previous Build

```bash
# Stop current deployment
sudo systemctl stop nginx

# Restore previous build
rm -rf /var/www/altshop-web/dist
cp -r /backups/altshop-web/dist-20260218 /var/www/altshop-web/dist

# Restart Nginx
sudo systemctl start nginx
```

### 2. Revert Configuration

```bash
# Restore previous config
cp /backups/nginx-config-20260218 /etc/nginx/sites-available/altshop-web
sudo nginx -t
sudo systemctl restart nginx
```

## Security Checklist

- [ ] HTTPS enabled
- [ ] Security headers configured
- [ ] CORS properly configured
- [ ] Environment variables secured
- [ ] Regular dependency updates
- [ ] SSL certificate auto-renewal enabled
- [ ] Firewall configured
- [ ] Rate limiting enabled
- [ ] Error pages customized

## Testing Before Deployment

### 1. Local Testing

```bash
npm run build
npm run preview
```

### 2. Staging Environment

Deploy to staging first:

```bash
vercel --environment staging
```

### 3. Production Testing

After deployment:
1. Test authentication flow
2. Test all pages
3. Test API integration
4. Test on different devices
5. Check browser console for errors

## Troubleshooting

### Issue: White Screen After Deployment

**Solution:**
- Check browser console for errors
- Verify base URL configuration
- Check API endpoint accessibility

### Issue: 404 on Page Refresh

**Solution:**
- Ensure server configured for SPA routing
- Verify `try_files` directive in Nginx

### Issue: API Calls Failing

**Solution:**
- Check CORS configuration
- Verify API base URL
- Check network tab in browser dev tools

## Post-Deployment Checklist

- [ ] Application loads correctly
- [ ] Authentication works
- [ ] All pages accessible
- [ ] API integration working
- [ ] Mobile responsive
- [ ] SSL certificate valid
- [ ] Error tracking configured
- [ ] Analytics working
- [ ] Performance acceptable
- [ ] Backups configured

## Support

For deployment issues:
1. Check logs
2. Review configuration
3. Test locally
4. Contact DevOps team

---

Last Updated: 2026-02-18
Version: 1.0.0
