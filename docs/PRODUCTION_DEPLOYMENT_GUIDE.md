# Production Deployment Guide - AltShop Bot ↔ Web Parity

**Version:** 1.0  
**Date:** February 21, 2026  
**Status:** Ready for Production Deployment

---

## 📋 Pre-Deployment Checklist

### Backend Preparation
- [ ] All API endpoints tested locally
- [ ] Database migrations ready
- [ ] Environment variables configured
- [ ] Docker image built and tested
- [ ] Public smoke endpoints working
- [ ] Logging configured
- [ ] Error monitoring setup (Sentry, etc.)

### Frontend Preparation
- [ ] OpenAPI types generated
- [ ] Production build successful
- [ ] All pages tested locally
- [ ] Environment variables configured
- [ ] CDN/Static hosting configured
- [ ] nginx configuration ready

### Database Preparation
- [ ] PostgreSQL production instance ready
- [ ] Database backups configured
- [ ] Connection pooling configured
- [ ] Migration scripts tested

### Infrastructure Preparation
- [ ] Docker Compose or Kubernetes configs ready
- [ ] Load balancer configured
- [ ] SSL certificates installed
- [ ] Domain DNS configured
- [ ] CDN configured (if applicable)

---

## 🚀 Deployment Steps

### Step 1: Backend Deployment

#### 1.1 Build Docker Image

```bash
cd D:\altshop-0.9.3

# Build backend image
docker build -t altshop-backend:latest .

# Tag for registry
docker tag altshop-backend:latest registry.example.com/altshop-backend:1.0.0

# Push to registry
docker push registry.example.com/altshop-backend:1.0.0
```

#### 1.2 Configure Environment Variables

Create `.env.production`:

```bash
# Database
DATABASE_URL=postgresql://user:password@db-host:5432/altshop

# Redis
REDIS_URL=redis://redis-host:6379/0

# Bot Configuration
BOT_TOKEN=your_bot_token
BOT_WEBHOOK_URL=https://remnabot.2get.pro/telegram

# Remnawave Panel
REMWAVE_URL=https://panel.example.com
REMWAVE_TOKEN=your_remnawave_token
REMWAVE_CADDY_TOKEN=your_caddy_token

# JWT Configuration
JWT_SECRET=your_jwt_secret
WEB_APP_JWT_SECRET=your_web_app_jwt_secret

# Frontend URL
FRONTEND_URL=https://remnabot.2get.pro

# Origins (comma-separated)
ORIGINS=https://remnabot.2get.pro,https://www.remnabot.2get.pro
```

#### 1.3 Deploy Backend

**Option A: Docker Compose**

```bash
# docker-compose.prod.yml
version: '3.8'

services:
  altshop:
    image: registry.example.com/altshop-backend:1.0.0
    env_file: .env.production
    ports:
      - "5000:5000"
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/v1/auth/access-status"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: altshop
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  postgres_data:
```

Deploy:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Option B: Kubernetes**

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: altshop-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: altshop-backend
  template:
    metadata:
      labels:
        app: altshop-backend
    spec:
      containers:
      - name: altshop
        image: registry.example.com/altshop-backend:1.0.0
        ports:
        - containerPort: 5000
        envFrom:
        - secretRef:
            name: altshop-secrets
        readinessProbe:
          httpGet:
            path: /api/v1/auth/access-status
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
```

Deploy:
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

#### 1.4 Run Database Migrations

```bash
# Inside backend container
docker exec -it altshop-backend-1 alembic upgrade head
```

#### 1.5 Verify Backend Deployment

```bash
# Health check
curl https://remnabot.2get.pro/api/v1/auth/access-status

# Test authentication
curl -X POST https://remnabot.2get.pro/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Test user endpoint
curl https://remnabot.2get.pro/api/v1/user/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Step 2: Frontend Deployment

#### 2.1 Generate OpenAPI Types

```bash
cd D:\altshop-0.9.3\web-app

# Make sure backend is running
npm run generate:api
```

#### 2.2 Configure Environment

Create `.env.production`:

```bash
VITE_API_BASE_URL=https://remnabot.2get.pro/api/v1
VITE_APP_NAME=AltShop
VITE_APP_VERSION=1.0.0
```

#### 2.3 Build Frontend

```bash
cd D:\altshop-0.9.3\web-app

# Install dependencies
npm install

# Generate types
npm run generate:api

# Build for production
npm run build

# Preview build locally
npm run preview
```

#### 2.4 Deploy Frontend

**Option A: nginx Static Hosting**

```bash
# Copy build to nginx
cp -r dist/* /opt/altshop/webapp/

# nginx configuration
server {
    server_name remnabot.2get.pro;
    
    listen 443 ssl;
    
    # Web App
    location /webapp/ {
        alias /opt/altshop/webapp/;
        index index.html;
        try_files $uri $uri/ /webapp/index.html;
    }
    
    # API Proxy
    location /api/v1 {
        proxy_pass http://altshop:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Option B: CDN Deployment**

```bash
# Upload to CDN (example with AWS S3)
aws s3 sync dist/ s3://altshop-cdn/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

#### 2.5 Verify Frontend Deployment

```bash
# Check main page
curl https://remnabot.2get.pro/webapp/

# Check assets
curl https://remnabot.2get.pro/webapp/assets/index-*.js

# Test in browser
# Open https://remnabot.2get.pro/webapp/
```

---

### Step 3: Post-Deployment Verification

#### 3.1 Critical User Journeys

Test these flows in production:

1. **User Registration**
   ```
   Visit /webapp/ → Register → Verify email → Login
   ```

2. **Purchase Flow**
   ```
   Login → Purchase Subscription → Select Plan → 
   Payment → Success → View Subscription
   ```

3. **Device Management**
   ```
   Login → Devices → Generate Link → Copy → Revoke
   ```

4. **Promocode Activation**
   ```
   Login → Promocodes → Enter Code → Activate
   ```

5. **Referral Program**
   ```
   Login → Referrals → Copy Link → View Stats
   ```

6. **Partner Withdrawal**
   ```
   Login → Partner → Request Withdrawal → Track Status
   ```

7. **Settings Update**
   ```
   Login → Settings → Update Profile → Save → Verify
   ```

#### 3.2 API Endpoint Testing

```bash
# Test all critical endpoints
ENDPOINTS=(
  "/api/v1/user/me"
  "/api/v1/subscription/list"
  "/api/v1/devices?subscription_id=1"
  "/api/v1/referral/info"
  "/api/v1/partner/info"
)

for endpoint in "${ENDPOINTS[@]}"; do
  echo "Testing $endpoint"
  curl -s -o /dev/null -w "%{http_code}" \
    https://remnabot.2get.pro$endpoint \
    -H "Authorization: Bearer YOUR_TOKEN"
  echo ""
done
```

#### 3.3 Performance Testing

```bash
# Install k6
# https://k6.io/docs/getting-started/installation/

# Run performance test
k6 run performance-test.js
```

Example performance test (`performance-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '30s',
};

export default function () {
  const res = http.get('https://remnabot.2get.pro/api/v1/user/me', {
    headers: { 'Authorization': 'Bearer YOUR_TOKEN' },
  });
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  sleep(1);
}
```

---

## 🔧 Monitoring & Maintenance

### Logging Configuration

```python
# Production logging config
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/altshop/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "default",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}
```

### Error Monitoring

**Sentry Integration:**

```bash
# Install sentry-sdk
pip install sentry-sdk[fastapi]
```

```python
# In main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[FastApiIntegration()],
    traces_sample_rate=1.0,
    environment="production",
)
```

### Performance Monitoring

**Prometheus + Grafana:**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

---

## 🔄 Rollback Procedure

### Backend Rollback

```bash
# 1. Stop current deployment
docker-compose -f docker-compose.prod.yml down

# 2. Pull previous version
docker pull registry.example.com/altshop-backend:0.9.3

# 3. Deploy previous version
docker tag altshop-backend:0.9.3 registry.example.com/altshop-backend:latest
docker-compose -f docker-compose.prod.yml up -d

# 4. Rollback database migrations
docker exec -it altshop-backend-1 alembic downgrade -1
```

### Frontend Rollback

```bash
# 1. Download previous build
aws s3 sync s3://altshop-backup/v0.9.3/ dist/

# 2. Deploy to CDN
aws s3 sync dist/ s3://altshop-cdn/ --delete

# 3. Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

---

## 📊 Success Criteria

### Performance Metrics
- API response time < 200ms (p95)
- Frontend load time < 2s
- Error rate < 0.1%
- Uptime > 99.9%

### Business Metrics
- User registration flow working
- Payment flow working
- All 7 user journeys functional
- Zero critical bugs

### Technical Metrics
- All health checks passing
- All tests passing
- No security vulnerabilities
- Logs flowing correctly

---

## 🎉 Deployment Complete Checklist

- [ ] Backend deployed and healthy
- [ ] Frontend deployed and accessible
- [ ] Database migrations applied
- [ ] All endpoints responding
- [ ] All user journeys tested
- [ ] Monitoring configured
- [ ] Logging configured
- [ ] Backups configured
- [ ] Rollback procedure tested
- [ ] Team notified
- [ ] Documentation updated
- [ ] Stakeholders notified

---

## 📞 Support Contacts

### Technical Team
- **Backend Lead:** [Contact]
- **Frontend Lead:** [Contact]
- **DevOps Lead:** [Contact]
- **Database Admin:** [Contact]

### Emergency Contacts
- **On-Call Engineer:** [Contact]
- **Project Manager:** [Contact]
- **CTO:** [Contact]

---

## 📚 Related Documentation

- `API_CONTRACT.md` - API reference
- `TROUBLESHOOTING.md` - Debug guide
- `SERVICE_INTEGRATION_GUIDE.md` - Integration patterns
- `BACKEND_OPERATOR_GUIDE.md` - Current backend runtime and deploy reference

---

**Deployment Guide Version:** 1.0  
**Last Updated:** 2026-02-21  
**Status:** Ready for Production ✅

**DEPLOY WITH CONFIDENCE!** 🚀
