# AltShop Landing Page Documentation

## Overview

Создана красивая лендинг-страница для пользователей, которая отображается при переходе на домен `remnabot.2get.pro`.

## Структура лендинга

### 1. Header (Шапка)
- Логотип AltShop
- Кнопка "Войти"

### 2. Hero Section (Главный экран)
- Заголовок с градиентным текстом
- Описание преимуществ
- Кнопка "Войти через Telegram"
- Статистика (пользователи, страны, uptime, поддержка)

### 3. Features Grid (Сетка возможностей)
6 карточек с иконками:
- ⚡ Мгновенная активация
- 📱 Все устройства (до 5)
- 🌍 Серверы по всему миру (50+ стран)
- 🛡️ Полная анонимность
- 🎧 Поддержка 24/7
- 🚀 Высокая скорость

### 4. Benefits Section (Преимущества)
Список преимуществ:
- Автоматическое продление подписки
- Гибкая система скидок и промокодов
- Реферальная программа
- Удобное управление через Telegram
- Моментальная техническая поддержка
- Гарантия возврата средств

### 5. Pricing Plans (Тарифные планы)
3 тарифа:
- **Старт** (1 месяц)
- **Оптимальный** (6 месяцев) - "Выбор пользователей"
- **Премиум** (12 месяцев) - "Максимальная выгода"

### 6. CTA Section (Призыв к действию)
Финальный блок с кнопкой входа

### 7. Footer (Подвал)
- Логотип
- Копирайт
- Ссылки на политику конфиденциальности и условия использования

## Дизайн особенности

### Цветовая схема
- **Фон**: Градиент от slate-900 через blue-900 к slate-900
- **Акценты**: Blue-600, Purple-600
- **Текст**: Белый для заголовков, gray-300/400 для описаний

### Эффекты
- Backdrop blur для карточек
- Градиентные границы
- Hover эффекты с transition
- Тени с color overlay
- Анимации при наведении

### Адаптивность
- Mobile-first подход
- Grid layout для карточек
- Flexbox для выравнивания
- Responsive typography

## Технические детали

### Компоненты

**File:** `src/pages/landing/LandingPage.tsx`

Используемые хуки:
- `useTelegramWebApp()` - определение среды (Telegram/браузер)
- `useNavigate()` - навигация после авторизации

Используемые UI компоненты:
- `Button` - кнопки
- `Card`, `CardContent` - карточки
- `Badge` - бейджи

Иконки (lucide-react):
- `Shield`, `Zap`, `Smartphone`, `Globe`, `Headphones`, `Rocket`
- `Check`, `ArrowRight`, `Star`, `Lock`, `Users`, `TrendingUp`

### Логика авторизации

#### Внутри Telegram (Mini App)
```typescript
if (isInTelegram && isReady && initData && queryId) {
  // Автоматическая авторизация через initData
  const { data } = await api.auth.telegram({ initData, queryId })
  setTokens(data.access_token, data.refresh_token)
  navigate('/dashboard')
}
```

#### В браузере
```typescript
// Перенаправление на Telegram бот
window.location.href = `https://t.me/${BOT_USERNAME}`
```

### Маршрутизация

**File:** `src/App.tsx`

```typescript
<Routes>
  {/* Landing page - главный вход */}
  <Route path="/" element={<LandingPage />} />
  
  {/* Login страница */}
  <Route path="/auth/login" element={<LoginPage />} />
  
  {/* Dashboard - защищённые роуты */}
  <Route path="/dashboard" element={<ProtectedRoute>
    <DashboardLayout />
  </ProtectedRoute}>
    {/* ... дочерние роуты */}
  </Route>
</Routes>
```

### Nginx конфигурация

**File:** `nginx/nginx.conf`

```nginx
# Landing Page - корневой домен
location = / {
    alias /opt/altshop/webapp/index.html;
    try_files /index.html =404;
}

# Web App (Mini App) - для Telegram
location /webapp/ {
    alias /opt/altshop/webapp/;
    try_files $uri $uri/ /index.html;
}

# Assets - кэширование на 1 год
location /assets/ {
    alias /opt/altshop/webapp/assets/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Как это работает

### Поток пользователя

```
┌─────────────────────────────────────────────────────────┐
│              Пользователь открывает домен                │
│              remnabot.2get.pro                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Landing Page         │
        │   - Красивый дизайн    │
        │   - Описание функций   │
        │   - Тарифные планы     │
        │   - Кнопка "Войти"     │
        └───────────┬────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
    В браузере           В Telegram
         │                     │
         │                     │
         ▼                     ▼
  Telegram Widget      Auto-auth через
         │             initData
         │                     │
         ▼                     ▼
    OAuth popup          JWT токены
         │                     │
         ▼                     ▼
    JWT токены           Dashboard
         │
         ▼
    Dashboard
```

### Определение среды

```typescript
const { isInTelegram, isReady, initData, queryId } = useTelegramWebApp()

// isInTelegram: true если приложение запущено внутри Telegram
// isReady: true если SDK инициализирован
// initData: строка для валидации на бэкенде
// queryId: идентификатор сессии
```

## Кастомизация

### Изменение текста

Все тексты находятся в `LandingPage.tsx`. Для изменения:

```typescript
// Hero section
<h1>Ваш заголовок</h1>

// Features
const features = [
  {
    title: 'Ваше название',
    description: 'Ваше описание',
  }
]

// Plans
const plans = [
  {
    name: 'Ваш тариф',
    duration: 'Период',
  }
]
```

### Изменение цветов

Цветовая схема в Tailwind CSS классах:

```typescript
// Фон
bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900

// Акценты
from-blue-600 to-purple-600

// Кнопки
bg-blue-600 hover:bg-blue-700
```

### Изменение статистики

```typescript
<div className="text-3xl md:text-4xl font-bold text-white mb-2">
  10K+  {/* Ваше значение */}
</div>
<div className="text-gray-400">
  Активных пользователей  {/* Ваше описание */}
</div>
```

## Тестирование

### В браузере

1. Откройте `https://remnabot.2get.pro/`
2. Проверьте:
   - ✅ Лендинг загружается
   - ✅ Все секции отображаются
   - ✅ Кнопка "Войти" работает
   - ✅ Адаптивность на мобильных

### В Telegram

1. Откройте бота
2. Нажмите Menu button
3. Проверьте:
   - ✅ Mini App открывается
   - ✅ Авто-авторизация работает
   - ✅ Перенаправление на dashboard

### Проверка консоли

Откройте DevTools (F12) и проверьте:
- Нет ошибок в Console
- Нет 404 в Network
- Assets загружаются с кэшем

## Производительность

### Оптимизации

1. **Кэширование assets** - 1 год (immutable)
2. **Gzip сжатие** - включено в nginx
3. **Code splitting** - vendor chunks разделены
4. **Lazy loading** - иконки загружаются по требованию

### Размеры файлов

```
index.html:        0.78 kB (gzip: 0.40 kB)
index.css:        49.15 kB (gzip: 8.66 kB)
react-vendor.js:  49.06 kB (gzip: 17.42 kB)
ui-vendor.js:     18.92 kB (gzip: 6.44 kB)
index.js:        520.58 kB (gzip: 152.01 kB)
```

## Будущие улучшения

### Возможные добавления

1. **Отзывы пользователей** - секция с testimonials
2. **FAQ** - часто задаваемые вопросы
3. **Видео демонстрация** - как работает сервис
4. **Сравнение тарифов** - детальная таблица
5. **Живой чат** - поддержка в реальном времени
6. **Мультиязычность** - переключатель языков
7. **Тёмная/светлая тема** - адаптация под тему Telegram

### A/B тестирование

- Разные варианты заголовков
- Разное расположение кнопок
- Разные цвета CTA
- Разное количество тарифов

## Поддержка

### Обновление контента

Для изменения текстов, цен или функций:

1. Отредактируйте `src/pages/landing/LandingPage.tsx`
2. Запустите `npm run build`
3. Перезапустите контейнеры: `docker compose restart altshop-nginx`

### Добавление новых секций

```typescript
// Новая секция
<section className="container mx-auto px-4 py-20">
  <div className="text-center mb-16">
    <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
      Ваш заголовок
    </h2>
  </div>
  
  {/* Контент секции */}
</section>
```

## Метрики

### Отслеживание

Для добавления аналитики:

```typescript
// Google Analytics
useEffect(() => {
  // GA code
}, [])

// Yandex Metrika
// Yandex code
```

### Конверсия

Ключевые метрики для отслеживания:
- Посещения → Клики на "Войти"
- Клики → Успешные авторизации
- Авторизации → Покупки

---

**Создано:** 2024
**Версия:** 1.0
**Последнее обновление:** 2024-02-19
