# AltShop - Authentication System Documentation

## ✅ Реализованная функциональность

### **Теперь пользователи могут:**

1. **Зарегистрироваться через браузер** с логином/паролем
2. **Войти через браузер** с логином/паролем  
3. **Пользоваться всеми функциями** из браузера (покупка, управление подпиской, устройства и т.д.)
4. **Telegram бот** остаётся для админов и как дополнительная опция входа

---

## 🔐 Система аутентификации

### **Методы входа:**

| Метод | Где работает | Описание |
|-------|--------------|----------|
| **Логин/пароль** | Браузер | Обычная регистрация через email/пароль |
| **Telegram** | Telegram Mini App | Авто-вход через initData |
| **Telegram Widget** | Браузер (опционально) | OAuth через Telegram |

---

## 📁 Новые файлы

### **Frontend:**

1. **`src/pages/auth/LoginPage.tsx`** - Страница входа
   - Форма входа (username + password)
   - Валидация
   - Обработка ошибок
   - Ссылка на регистрацию

2. **`src/pages/auth/RegisterPage.tsx`** - Страница регистрации
   - Форма регистрации (Telegram ID + username + password)
   - Валидация пароля (мин. 6 символов, совпадение)
   - Валидация Telegram ID (только цифры)
   - Подсказки по требованиям
   - Ссылка на вход

3. **`src/lib/api.ts`** - Обновлён API клиент
   ```typescript
   auth: {
     login: (username, password) => POST /api/v1/auth/login
     register: (telegram_id, username, password) => POST /api/v1/auth/register
     telegram: (initData, ...) => POST /api/v1/auth/telegram
     refresh: (refresh_token) => POST /api/v1/auth/refresh
     logout: () => POST /api/v1/auth/logout
   }
   ```

4. **`src/App.tsx`** - Добавлены роуты
   ```typescript
   /auth/login → LoginPage
   /auth/register → RegisterPage
   ```

5. **`src/pages/landing/LandingPage.tsx`** - Обновлён лендинг
   - Кнопка "Войти" → ведёт на `/auth/login`
   - Кнопка "Зарегистрироваться" → ведёт на `/auth/register`
   - Кнопка "Начать бесплатно" → ведёт на `/auth/register`

---

## 🎯 Пользовательский поток

### **Регистрация:**

```
1. Пользователь заходит на https://remnabot.2get.pro/
   ↓
2. Видит лендинг с описанием
   ↓
3. Нажимает "Зарегистрироваться" или "Начать бесплатно"
   ↓
4. Попадает на страницу регистрации
   ↓
5. Вводит:
   - Telegram ID (узнаёт через @userinfobot)
   - Username (придумывает)
   - Пароль (мин. 6 символов)
   - Подтверждение пароля
   ↓
6. Отправляет форму
   ↓
7. Backend создаёт аккаунт
   ↓
8. Возвращает JWT токены
   ↓
9. Перенаправление на /dashboard
```

### **Вход:**

```
1. Пользователь заходит на https://remnabot.2get.pro/
   ↓
2. Нажимает "Войти"
   ↓
3. Попадает на страницу входа
   ↓
4. Вводит username + пароль
   ↓
5. Отправляет форму
   ↓
6. Backend проверяет credentials
   ↓
7. Возвращает JWT токены
   ↓
8. Перенаправление на /dashboard
```

---

## 🖥️ Доступные функции в браузере

После входа пользователь имеет доступ ко **всем пользовательским функциям**:

| Функция | Описание |
|---------|----------|
| **Dashboard** | Главная панель со статистикой |
| **Подписка** | Просмотр текущей подписки |
| **Покупка** | Покупка новой подписки |
| **Продление** | Продление существующей |
| **Устройства** | Управление устройствами (просмотр, добавление, отзыв) |
| **Рефералы** | Просмотр рефералов, статистика |
| **Промокоды** | Активация промокодов |
| **Партнерка** | Участие в партнёрской программе |
| **Настройки** | Настройки аккаунта |

---

## 🔒 Telegram бот (для админов)

**Telegram бот остаётся для:**

- **DEV** - полный доступ
- **ADMIN** - управление пользователями, рассылки, настройки
- **Пользователи** - могут пользоваться ботом как альтернативой веб-интерфейсу

### **Функции бота:**

| Роль | Доступ |
|------|--------|
| **DEV** | Все функции + администрирование |
| **ADMIN** | Управление пользователями, рассылки, настройки |
| **USER** | Покупка, управление подпиской через бот |

---

## 📝 Требования к бэкенду

### **Необходимые API endpoints:**

```typescript
POST /api/v1/auth/register
Body: {
  telegram_id: number
  username: string
  password: string (hashed)
}
Response: {
  expires_in: number
  is_new_user?: boolean
  auth_source?: string | null
}

POST /api/v1/auth/login
Body: {
  username: string
  password: string
}
Response: {
  expires_in: number
  is_new_user?: boolean
  auth_source?: string | null
}

POST /api/v1/auth/refresh
Body: {}
Response: {
  expires_in: number
}

POST /api/v1/auth/logout
Response: { message: string }
```

---

## 🗄️ База данных

### **Таблица users (должна поддерживать):**

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,        -- Telegram ID для связи с ботом
    username VARCHAR UNIQUE NOT NULL, -- Логин для входа
    password_hash VARCHAR NOT NULL,   -- Хэш пароля
    name VARCHAR,
    role VARCHAR DEFAULT 'USER',      -- USER, ADMIN, DEV
    language VARCHAR DEFAULT 'ru',
    personal_discount INT DEFAULT 0,
    purchase_discount INT DEFAULT 0,
    points INT DEFAULT 0,
    is_blocked BOOLEAN DEFAULT FALSE,
    is_bot_blocked BOOLEAN DEFAULT FALSE,
    is_rules_accepted BOOLEAN DEFAULT TRUE,
    max_subscriptions INT,
    current_subscription_id INT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

## 🔐 Безопасность

### **Пароли:**

- Минимальная длина: **6 символов**
- Хранение: **bcrypt/argon2 хэш**
- Передача: **только по HTTPS**

### **JWT токены:**

- **Access token:** 7 дней (настраивается)
- **Refresh token:** 30 дней (настраивается)
- Хранение: **localStorage** (frontend)

### **Валидация:**

- Telegram ID: **только цифры**
- Username: **уникальный**
- Password: **совпадение подтверждений**

---

## 🎨 UI/UX особенности

### **Страница регистрации:**

- ✅ Визуальная валидация пароля (галочки/крестики)
- ✅ Подсказки по требованиям
- ✅ Проверка Telegram ID
- ✅ Индикация загрузки
- ✅ Обработка ошибок

### **Страница входа:**

- ✅ Простая форма (2 поля)
- ✅ Индикация загрузки
- ✅ Обработка ошибок
- ✅ Ссылка на регистрацию

### **Лендинг:**

- ✅ 2 кнопки: "Войти" + "Зарегистрироваться"
- ✅ Призыв к действию
- ✅ Статистика
- ✅ Тарифные планы

---

## 🧪 Тестирование

### **Проверка регистрации:**

```bash
# 1. Откройте https://remnabot.2get.pro/
# 2. Нажмите "Зарегистрироваться"
# 3. Заполните форму:
#    - Telegram ID: 123456789
#    - Username: testuser
#    - Password: test123456
#    - Confirm: test123456
# 4. Отправьте форму
# 5. Должна перекинуть на /dashboard
```

### **Проверка входа:**

```bash
# 1. Откройте https://remnabot.2get.pro/auth/login
# 2. Введите username и пароль
# 3. Отправьте форму
# 4. Должна перекинуть на /dashboard
```

### **Проверка доступа к функциям:**

```bash
# После входа проверьте:
# ✅ Dashboard открывается
# ✅ Подписка отображается
# ✅ Можно купить подписку
# ✅ Можно управлять устройствами
# ✅ Рефералы отображаются
# ✅ Промокоды работают
```

---

## 📊 Метрики

### **Конверсия:**

- Посещения → Регистрации
- Регистрации → Покупки
- Входы → Активные пользователи

### **Отслеживание:**

Добавьте аналитику для отслеживания:
```typescript
// Google Analytics
gtag('event', 'registration', { method: 'username_password' })
gtag('event', 'login', { method: 'username_password' })
```

---

## 🔄 Миграция с Telegram auth

Если у пользователя уже есть аккаунт через Telegram:

### **Вариант 1: Автоматическая привязка**

При первой авторизации через Telegram:
```typescript
if (telegramUserExists) {
  // Привязать username к существующему аккаунту
  await updateUser(telegramId, { username, passwordHash })
}
```

### **Вариант 2: Ручная привязка**

Пользователь вводит Telegram ID при регистрации:
```typescript
// Проверить совпадение Telegram ID
const existingUser = await getUserByTelegramId(telegramId)
if (existingUser) {
  // Обновить данные
  await updateUser(existingUser.id, { username, passwordHash })
}
```

---

## 📱 Адаптивность

Все страницы полностью адаптивны:

- ✅ Mobile (320px+)
- ✅ Tablet (768px+)
- ✅ Desktop (1024px+)

---

## 🚀 Следующие шаги

### **Опциональные улучшения:**

1. **Восстановление пароля** - email/SMS верификация
2. **2FA** - двухфакторная аутентификация
3. **Email верификация** - подтверждение email
4. **Социальные сети** - Google, Facebook OAuth
5. **Remember me** - долгоживущие сессии
6. **Session management** - просмотр активных сессий

---

**Дата создания:** 2024-02-19  
**Версия:** 1.0  
**Статус:** ✅ Готово к использованию
