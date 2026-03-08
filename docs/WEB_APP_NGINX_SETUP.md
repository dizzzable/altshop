# Web App Deployment Guide (nginx reverse proxy)

## 📋 Обзор

Web App работает через nginx reverse proxy на порту 443 вместе с ботом.

```
┌─────────────────────────────────────────────────────────┐
│                    nginx (443)                          │
│                   remnabot.2get.pro                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  /webapp    -> static files from /opt/altshop/webapp   │
│  /api/v1    → altshop:5000 (FastAPI backend)           │
│  /telegram  → altshop:5000 (Telegram webhook)          │
│  /remnawave → altshop:5000 (Remnawave webhook)         │
│  /payments  → altshop:5000 (Payment webhooks)          │
│  /          -> 302 redirect to /webapp/                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Развёртывание

### Шаг 1: Соберите frontend приложение

```bash
# Для React (Vite)
cd web-app
npm install
npm run build
# Build будет в web-app/dist/

# Для Next.js
cd web-app
npm install
npm run build
# Скопируйте output из .next/static в dist/
```

### Шаг 2: Проверьте структуру файлов

```
web-app/
└── dist/
    ├── index.html
    ├── assets/
    │   ├── index-abc123.css
    │   └── index-xyz789.js
    └── favicon.ico
```

### Шаг 3: Обновите .env

```env
# Web App Configuration
WEB_APP_ENABLED=true
WEB_APP_URL=https://remnabot.2get.pro/webapp
WEB_APP_JWT_SECRET=ваш_секретный_ключ_минимум_32_символа
WEB_APP_API_SECRET_TOKEN=ещё_один_секретный_ключ
WEB_APP_CORS_ORIGINS=https://remnabot.2get.pro
```

### Шаг 4: Запустите контейнеры

```bash
# Optional if you use a remote image registry
docker compose pull

# Build frontend dist (one-shot)
docker compose up -d --build webapp-build

# Start runtime services
docker compose up -d --build altshop altshop-taskiq-worker altshop-taskiq-scheduler altshop-nginx
```

### Шаг 5: Проверьте работу

```bash
# Проверка nginx конфигурации
docker compose exec altshop-nginx nginx -t

# Проверка webapp контейнера
docker compose exec altshop-nginx ls -lah /opt/altshop/webapp
docker compose exec altshop-nginx test -f /opt/altshop/webapp/index.html
# Проверка доступности
curl -I https://remnabot.2get.pro/
curl -I https://remnabot.2get.pro/webapp/
curl -I https://remnabot.2get.pro/api/v1/auth/access-status
```

## 📁 Файловая структура

```
altshop-0.9.3/
├── docker-compose.yml       # Основной compose файл
├── .env                     # Переменные окружения
├── nginx/
│   ├── nginx.conf           # Основная конфигурация nginx
│   ├── fullchain.pem
│   └── privkey.key
└── web-app/
    └── dist/                # Build файлы frontend
        ├── index.html
        └── assets/
```

## 🔧 Настройка frontend приложения

### React (Vite)

```javascript
// vite.config.js
export default {
  server: {
    proxy: {
      '/api': 'https://remnabot.2get.pro'
    }
  },
  build: {
    outDir: 'dist',
    base: '/webapp/'
  }
}
```

### Vue 3

```javascript
// vite.config.js
export default {
  base: '/webapp/',
  server: {
    proxy: {
      '/api': 'https://remnabot.2get.pro'
    }
  }
}
```

### Next.js

```javascript
// next.config.js
module.exports = {
  basePath: '/webapp',
  assetPrefix: '/webapp/',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://remnabot.2get.pro/api/:path*'
      }
    ]
  }
}
```

## 🔐 CORS настройка

Frontend должен делать запросы на тот же домен:

```javascript
// Правильно (тот же домен)
fetch('https://remnabot.2get.pro/api/v1/auth/telegram')

// В .env
WEB_APP_CORS_ORIGINS=https://remnabot.2get.pro
```

## 📊 Маршрутизация

| URL | Описание | Контейнер |
|-----|----------|-----------|
| `https://remnabot.2get.pro/webapp` | Web App frontend | altshop-nginx (static alias `/webapp/`) |
| `https://remnabot.2get.pro/api/v1/*` | API endpoints | altshop:5000 |
| `https://remnabot.2get.pro/telegram` | Telegram webhook | altshop:5000 |
| `https://remnabot.2get.pro/` | Redirect to web landing | altshop-nginx |

## 🧪 Тестирование

### 1. Проверка nginx

```bash
docker compose exec altshop-nginx nginx -t
# nginx: configuration file test is successful
```

### 2. Проверка webapp контейнера

```bash
docker compose exec altshop-nginx ls -lah /opt/altshop/webapp
docker compose exec altshop-nginx test -f /opt/altshop/webapp/index.html
# Должно быть: "nginx: started"
```

### 3. Проверка доступности

```bash
# Web App health check
curl -I https://remnabot.2get.pro/
curl -I https://remnabot.2get.pro/webapp/
curl -I https://remnabot.2get.pro/api/v1/auth/access-status
# Ответ: HTTP 200

# Web App index
curl https://remnabot.2get.pro/webapp/
# Ответ: HTML страница

# API endpoint
curl https://remnabot.2get.pro/api/v1/auth/access-status
# Ответ: JSON от backend
```

## 🔍 Troubleshooting

### Ошибка 502 Bad Gateway

```bash
# Проверьте что webapp контейнер запущен
docker compose ps altshop-nginx

# Проверьте логи
docker compose exec altshop-nginx ls -lah /opt/altshop/webapp
docker compose exec altshop-nginx test -f /opt/altshop/webapp/index.html
# Проверьте что файлы существуют
docker compose exec altshop-nginx ls -la /opt/altshop/webapp
```

### Ошибка 404 Not Found

```bash
# Проверьте что index.html существует
docker compose exec altshop-nginx cat /opt/altshop/webapp/index.html

# Проверьте nginx конфигурацию
docker compose exec altshop-nginx nginx -t
```

If `GET /webapp/index.html` returns `404`, verify that `web-app/dist/index.html` exists and is mounted to `/opt/altshop/webapp`. If it returns `500`, verify nginx routing blocks below.

```nginx
location = /webapp/ {
    root /opt/altshop;
    try_files /webapp/index.html =404;
}

location = /webapp/index.html {
    alias /opt/altshop/webapp/index.html;
}

location /webapp/ {
    alias /opt/altshop/webapp/;
    try_files $uri $uri/ /webapp/index.html;
}
```

### CORS ошибки в браузере

```bash
# Проверьте WEB_APP_CORS_ORIGINS в .env
# Должен совпадать с доменом

# Перезапустите контейнеры
docker compose restart altshop
```

## 📝 Пример frontend приложения

```html
<!-- web-app/dist/index.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Web App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>
    <div id="root"></div>
    <script>
        // Инициализация Telegram WebApp
        const tg = window.Telegram.WebApp;
        tg.ready();
        
        // Получаем данные пользователя
        const user = tg.initDataUnsafe.user;
        console.log('User:', user);
        
        // Отправляем данные на backend
        fetch('/api/v1/auth/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tg.initDataUnsafe)
        })
        .then(res => res.json())
        .then(data => {
            localStorage.setItem('token', data.access_token);
        });
    </script>
</body>
</html>
```

## 🎯 Итог

После настройки:

1. ✅ Web App доступен по `https://remnabot.2get.pro/webapp`
2. ✅ API доступно по `https://remnabot.2get.pro/api/v1`
3. ✅ Всё работает через порт 443
4. ✅ SSL сертификаты используются из `/etc/nginx/ssl/`
5. ✅ Не нужно открывать дополнительные порты


---

## 2026-02-21 Canonical Runbook (Authoritative)

Use this sequence for deterministic deployment of `/webapp`:

```bash
# Optional: only if images are pulled from registry
docker compose pull

# Build static web files (one-shot)
docker compose up -d --build webapp-build

# Start runtime services
docker compose up -d --build altshop altshop-taskiq-worker altshop-taskiq-scheduler altshop-nginx

# Verify static mount and entry file
docker compose exec altshop-nginx ls -lah /opt/altshop/webapp
docker compose exec altshop-nginx test -f /opt/altshop/webapp/index.html

# Smoke checks
curl -I https://remnabot.2get.pro/
curl -I https://remnabot.2get.pro/
curl -I https://remnabot.2get.pro/webapp/
curl -I https://remnabot.2get.pro/api/v1/auth/access-status
curl -I https://remnabot.2get.pro/api/v1/auth/access-status
```

Canonical nginx webapp routing:

```nginx
location = /webapp/ {
    root /opt/altshop;
    try_files /webapp/index.html =404;
}

location = /webapp/index.html {
    alias /opt/altshop/webapp/index.html;
}

location /webapp/ {
    alias /opt/altshop/webapp/;
    index index.html;
    try_files $uri $uri/ /webapp/index.html;
}
```

Diagnostics:
- If `/opt/altshop/webapp/index.html` exists, `/webapp/` should return `200`.
- If `index.html` is missing, `/webapp/` should return `404` (not `500` rewrite cycle).




