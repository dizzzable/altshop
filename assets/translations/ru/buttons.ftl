# Back
btn-back = ⬅️ Назад
btn-main-menu = ↩️ Главное меню
btn-back-main-menu = ↩️ Вернуться в главное меню
btn-back-dashboard = ↩️ Вернуться в панель управления


# Remnashop
btn-remnashop-release-latest = 👀 Посмотреть
btn-remnashop-how-upgrade = ❓ Как обновить
btn-remnashop-github = ⭐ GitHub
btn-remnashop-telegram = 👪 Telegram
btn-remnashop-donate = 💰 Поддержать разработчика
btn-remnashop-guide = ❓ Инструкция


# Other
btn-rules-accept = ✅ Принять правила
btn-channel-join = ❤️ Перейти в канал
btn-channel-confirm = ✅ Подтвердить
btn-notification-close = ❌ Закрыть
btn-contact-support = 📩 Перейти в поддержку

btn-squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }


# Menu
btn-menu-connect = 🚀 Подключиться

btn-menu-connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] ПРЕВЫШЕН ЛИМИТ ТРАФИКА
    [EXPIRED] СРОК ДЕЙСТВИЯ ИСТЕК
    *[OTHER] ВАША ПОДПИСКА НЕ РАБОТАЕТ
    } ⚠️

btn-menu-trial = 🎁 ПОПРОБОВАТЬ БЕСПЛАТНО
btn-menu-devices = 📱 Мои устройства ({ $count })
btn-menu-devices-empty = ⚠️ Нет привязанных устройств
btn-menu-devices-subscription = { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $plan_name } ({ $device_count } устр.)
btn-menu-devices-get-url = 🔗 Получить ссылку
btn-menu-subscription = 💳 Подписка ({ $count })
btn-menu-invite = 👥 Пригласить
btn-menu-invite-about = ❓ Подробнее о награде
btn-menu-invite-copy = 🔗 Скопировать ссылку
btn-menu-invite-send = 📩 Пригласить
btn-menu-invite-qr = 🧾 QR-код
btn-menu-invite-withdraw-points = 💎 Обменять баллы
btn-menu-exchange = 🎁 Награды
btn-menu-exchange-select-type = 🔄 Выбрать тип обмена
btn-menu-exchange-points = ⏳ Обменять на дни подписки
btn-menu-exchange-days = ⏳ Добавить дни к подписке
btn-menu-exchange-gift = 🎁 Получить подарочный промокод
btn-menu-exchange-gift-select-plan = 📦 Выбрать план
btn-menu-exchange-discount = 💸 Получить скидку
btn-menu-exchange-traffic = 🌐 Добавить трафик
btn-menu-exchange-points-confirm = ✅ Подтвердить обмен
btn-menu-exchange-gift-confirm = 🎁 Получить промокод
btn-menu-exchange-discount-confirm = 💸 Получить скидку { $discount_percent }% ({ $points_to_spend } баллов)
btn-menu-exchange-traffic-confirm = 🌐 Добавить { $traffic_gb } ГБ ({ $points_to_spend } баллов)
btn-menu-copy-promocode = 📋 Скопировать промокод

btn-menu-exchange-type-choice = { $available ->
    [1] { $type ->
        [SUBSCRIPTION_DAYS] ⏳ Дни подписки
        [GIFT_SUBSCRIPTION] 🎁 Подарочная подписка
        [DISCOUNT] 💸 Скидка на покупку
        [TRAFFIC] 🌐 Доп. трафик
        *[OTHER] { $type }
        }
    *[0] ❌ { $type ->
        [SUBSCRIPTION_DAYS] Дни подписки (недоступно)
        [GIFT_SUBSCRIPTION] Подарочная подписка (недоступно)
        [DISCOUNT] Скидка (недоступно)
        [TRAFFIC] Трафик (недоступно)
        *[OTHER] { $type }
        }
    }
btn-menu-support = � Поддержка
btn-menu-dashboard = 🛠 Панель управления


# Dashboard
btn-dashboard-statistics = 📊 Статистика
btn-dashboard-users = 👥 Пользователи
btn-dashboard-broadcast = 📢 Рассылка
btn-dashboard-promocodes = 🎟 Промокоды
btn-dashboard-access = 🔓 Режим доступа
btn-dashboard-remnawave = 🌊 RemnaWave
btn-dashboard-remnashop = 🛍 RemnaShop
btn-dashboard-importer = 📥 Импорт пользователей


# Statistics
btn-statistics-page =
    { $target_page1 ->
    [1] 👥
    [2] 🧾
    [3] 💳
    [4] 📦
    [5] 🎁
    [6] 👪
    *[OTHER] page
    }

btn-statistics-current-page =
    { $current_page1 ->
    [1] [👥]
    [2] [🧾]
    [3] [💳]
    [4] [📦]
    [5] [🎁]
    [6] [👪]
    *[OTHER] [page]
    }


# Users
btn-users-search = 🔍 Поиск пользователя
btn-users-recent-registered = 🆕 Последние зарегистрированные
btn-users-recent-activity = 📝 Последние взаимодействующие
btn-users-blacklist = 🚫 Черный список
btn-users-unblock-all = 🔓 Разблокировать всех


# User
btn-user-discount = 💸 Изменить скидку
btn-user-points = 💎 Изменить баллы
btn-user-statistics = 📊 Статистика
btn-user-message = 📩 Сообщение
btn-user-role = 👮‍♂️ Изменить роль
btn-user-transactions = 🧾 Транзакции
btn-user-give-access = 🔑 Доступ к планам
btn-user-current-subscription = 💳 Текущая подписка
btn-user-subscription-traffic-limit = 🌐 Лимит трафика
btn-user-subscription-device-limit = 📱 Лимит устройств
btn-user-subscription-expire-time = ⏳ Время истечения
btn-user-subscription-squads = 🔗 Сквады
btn-user-subscription-traffic-reset = 🔄 Сбросить трафик
btn-user-subscription-devices = 🧾 Список устройств
btn-user-subscription-url = 📋 Скопировать ссылку
btn-user-subscription-set = ✅ Установить подписку
btn-user-subscription-delete = ❌ Удалить
btn-user-message-preview = 👀 Предпросмотр
btn-user-message-confirm = ✅ Отправить
btn-user-sync = 🌀 Синхронизировать
btn-user-give-subscription = 🎁 Выдать подписку
btn-user-subscription-internal-squads = ⏺️ Внутренние сквады
btn-user-subscription-external-squads = ⏹️ Внешний сквад

btn-user-allowed-plan-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $plan_name }

btn-user-subscription-active-toggle = { $is_active ->
    [1] 🔴 Выключить
    *[0] 🟢 Включить
    }

btn-user-transaction = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [CANCELED] ❌
    [REFUNDED] 💸
    [FAILED] ⚠️
    *[OTHER] { $status }
} { $created_at }

btn-user-block = { $is_blocked ->
    [1] 🔓 Разблокировать
    *[0] 🔒 Заблокировать
    }

btn-user-partner = 👾 Партнерка
btn-user-partner-balance = 💰 Изменить баланс
btn-user-partner-create = ✅ Выдать партнерку
btn-user-partner-toggle = { $is_active ->
    [1] 🔴 Деактивировать
    *[0] 🟢 Активировать
    }
btn-user-partner-delete = ❌ Удалить партнерку
btn-user-partner-withdrawals = 💸 Заявки на вывод
btn-user-partner-withdrawal = { $status ->
    [PENDING] 🕓
    [APPROVED] ✅
    [REJECTED] ❌
    *[OTHER] { $status }
    } { $amount } - { $created_at }
btn-user-partner-withdrawal-approve = ✅ Одобрить
btn-user-partner-withdrawal-reject = ❌ Отклонить
btn-user-partner-settings = ⚙️ Индивидуальные настройки
btn-user-partner-use-global = { $use_global ->
    [1] 🔘 Глобальные настройки
    *[0] ⚪ Индивидуальные настройки
    }
btn-user-partner-accrual-strategy = 📍 Условие начисления
btn-user-partner-reward-type = 🎀 Тип награды
btn-user-partner-percents = 📊 Проценты по уровням
btn-user-partner-fixed-amounts = 💰 Фиксированные суммы
btn-user-partner-accrual-strategy-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $strategy ->
    [ON_FIRST_PAYMENT] 💳 Только первый платеж
    [ON_EACH_PAYMENT] 💸 Каждый платеж
    *[OTHER] { $strategy }
    }
btn-user-partner-reward-type-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $reward_type ->
    [PERCENT] 📊 Процент от оплаты
    [FIXED_AMOUNT] 💰 Фиксированная сумма
    *[OTHER] { $reward_type }
    }
btn-user-partner-level-percent = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } уровень: { $percent }%
btn-user-partner-level-fixed = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } уровень: { $amount } руб.


# Broadcast
btn-broadcast-list = 📄 Список всех рассылок
btn-broadcast-all = 👥 Всем
btn-broadcast-plan = 📦 По плану
btn-broadcast-subscribed = ✅ С подпиской
btn-broadcast-unsubscribed = ❌ Без подписки
btn-broadcast-expired = ⌛ Просроченным
btn-broadcast-trial = ✳️ С пробником
btn-broadcast-content = ✉️ Редактировать содержимое
btn-broadcast-buttons = ✳️ Редактировать кнопки
btn-broadcast-preview = 👀 Предпросмотр
btn-broadcast-confirm = ✅ Запустить рассылку
btn-broadcast-refresh = 🔄 Обновить данные
btn-broadcast-viewing = 👀 Просмотр
btn-broadcast-cancel = ⛔ Остановить рассылку
btn-broadcast-delete = ❌ Удалить отправленное

btn-broadcast-button-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    }

btn-broadcast =  { $status ->
    [PROCESSING] ⏳
    [COMPLETED] ✅
    [CANCELED] ⛔
    [DELETED] ❌
    [ERROR] ⚠️
    *[OTHER] { $status }
} { $created_at }


# Go to
btn-goto-subscription = 💳 Купить подписку
btn-goto-promocode = 🎟 Активировать промокод
btn-goto-subscription-renew = 🔄 Продлить подписку
btn-goto-user-profile = 👤 Перейти к пользователю


# Promocodes
btn-promocodes-list = 📃 Список промокодов
btn-promocodes-search = 🔍 Поиск промокода
btn-promocodes-create = 🆕 Создать
btn-promocodes-delete = 🗑️ Удалить
btn-promocodes-edit = ✏️ Редактировать


# Access
btn-access-mode = { access-mode }
btn-access-conditions = ⚙️ Условия доступа
btn-access-rules = ✳️ Принятие правил
btn-access-channel = ❇️ Подписка на канал

btn-access-condition-toggle = { $enabled ->
    [1] 🔘 Включено
    *[0] ⚪ Выключено
    }


# RemnaShop
btn-remnashop-admins = 👮‍♂️ Администраторы
btn-remnashop-gateways = 🌐 Платежные системы
btn-remnashop-referral = 👥 Реф. система
btn-remnashop-partner = 👾 Партнерка
btn-remnashop-withdrawal-requests = 📝 Запросы на вывод ({ $count })
btn-remnashop-advertising = 🎯 Реклама
btn-remnashop-plans = 📦 Планы
btn-remnashop-notifications = 🔔 Уведомления
btn-remnashop-banners = 🖼️ Баннеры
btn-remnashop-logs = 📄 Логи
btn-remnashop-audit = 🔍 Аудит

# Banners
btn-banner-item = 🖼️ { $name }
btn-banner-locale-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $locale }
btn-banner-upload = 📤 Загрузить
btn-banner-delete = 🗑️ Удалить
btn-banner-confirm-delete = ❌ Подтвердить удаление


# Gateways
btn-gateway-title = { gateway-type }
btn-gateways-setting = { $field }
btn-gateways-webhook-copy = 📋 Скопировать вебхук

btn-gateway-active = { $is_active ->
    [1] 🟢 Включено
    *[0] 🔴 Выключено
    }

btn-gateway-test = 🐞 Тест
btn-gateways-default-currency = 💸 Валюта по умолчанию
btn-gateways-placement = 🔢 Изменить позиционирование

btn-gateways-default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }


# Referral
btn-referral-level = 🔢 Уровень
btn-referral-reward-type = 🎀 Тип награды
btn-referral-accrual-strategy = 📍 Условие начисления
btn-referral-reward-strategy = ⚖️ Форма начисления
btn-referral-reward = 🎁 Награда
btn-referral-eligible-plans = 📦 Тарифы для наград
btn-referral-clear-filter = 🗑️ Сбросить фильтр
btn-referral-points-exchange = 💎 Настройки обмена баллов
btn-referral-exchange-enable = { $exchange_enabled ->
    [1] 🟢 Обмен включен
    *[0] 🔴 Обмен выключен
    }
btn-referral-exchange-types = 🔄 Типы обмена ({ $enabled_types_count })
btn-referral-points-per-day = 📊 Курс обмена ({ $points_per_day } балл = 1 день)
btn-referral-min-exchange = ⬇️ Мин. баллов ({ $min_exchange_points })
btn-referral-max-exchange = ⬆️ Макс. баллов ({ $max_exchange_points ->
    [-1] ∞
    *[other] { $max_exchange_points }
    })

btn-referral-exchange-type-choice = { $enabled ->
    [1] 🟢
    *[0] 🔴
    } { $type ->
    [SUBSCRIPTION_DAYS] ⏳ Дни подписки
    [GIFT_SUBSCRIPTION] 🎁 Подарочная подписка
    [DISCOUNT] 💸 Скидка на покупку
    [TRAFFIC] 🌐 Доп. трафик
    *[OTHER] { $type }
    }

btn-referral-exchange-type-enable = { $enabled ->
    [1] 🟢 Включен
    *[0] 🔴 Выключен
    }

btn-referral-exchange-type-cost = 💰 Стоимость ({ $points_cost } баллов)
btn-referral-exchange-type-min = ⬇️ Мин. баллов ({ $min_points })
btn-referral-exchange-type-max = ⬆️ Макс. баллов ({ $max_points ->
    [-1] ∞
    *[other] { $max_points }
    })

btn-referral-gift-plan = 📦 План ({ $gift_plan_name })
btn-referral-gift-duration = ⏳ Длительность ({ $gift_duration_days } дней)
btn-referral-discount-max = 💸 Макс. скидка ({ $max_discount_percent }%)
btn-referral-traffic-max = 🌐 Макс. трафик ({ $max_traffic_gb } ГБ)

btn-referral-gift-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $is_active ->
    [1] 🟢
    *[0] 🔴
    } { $plan_name }

btn-referral-eligible-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $is_active ->
    [1] 🟢
    *[0] 🔴
    } { $plan_name }

btn-referral-enable = { $is_enable -> 
    [1] 🟢 Включена
    *[0] 🔴 Выключена
    }

btn-referral-level-choice = { $type -> 
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $type }
    }

btn-referral-reward-choice = { $type -> 
    [POINTS] 💎 Баллы
    [EXTRA_DAYS] ⏳ Дни
    *[OTHER] { $type }
    }

btn-referral-accrual-strategy-choice = { $type -> 
    [ON_FIRST_PAYMENT] 💳 Первый платеж
    [ON_EACH_PAYMENT] 💸 Каждый платеж
    *[OTHER] { $type }
    }

btn-referral-reward-strategy-choice = { $type -> 
    [AMOUNT] 🔸 Фиксированная
    [PERCENT] 🔹 Процентная
    *[OTHER] { $type }
    }


# Notifications
btn-notifications-user = 👥 Пользовательские

btn-notifications-user-choice = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] Подписка истекает (3 дня)
    [EXPIRES_IN_2_DAYS] Подписка истекает (2 дня)
    [EXPIRES_IN_1_DAYS] Подписка истекает (1 день)
    [EXPIRED] Подписка истекла
    [LIMITED] Трафик исчерпан
    [EXPIRED_1_DAY_AGO] Подписка истекла (1 день)
    [REFERRAL_ATTACHED] Реферал закреплен
    [REFERRAL_REWARD] Получено вознаграждение
    *[OTHER] { $type }
    }

btn-notifications-system = ⚙️ Системные

btn-notifications-system-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [BOT_LIFETIME] Жизненный цикл бота
    [BOT_UPDATE] Обновления бота
    [USER_REGISTERED] Регистрация пользователя
    [SUBSCRIPTION] Оформление подписки
    [PROMOCODE_ACTIVATED] Активация промокода
    [TRIAL_GETTED] Получение пробника
    [NODE_STATUS] Статус узла
    [USER_FIRST_CONNECTED] Первое подключение
    [USER_HWID] Устройства пользователя
    *[OTHER] { $type }
    }


# Plans
btn-plans-statistics = 📊 Статистика
btn-plans-create = 🆕 Создать
btn-plan-save = ✅ Сохранить
btn-plan-create = ✅ Создать план
btn-plan-delete = ❌ Удалить
btn-plan-name = 🏷️ Название
btn-plan-description = 💬 Описание
btn-plan-description-remove = ❌ Удалить текущее описание
btn-plan-tag = 📌 Тег
btn-plan-tag-remove = ❌ Удалить текущий тег
btn-plan-type = 🔖 Тип
btn-plan-availability = ✴️ Доступ
btn-plan-durations-prices = ⏳ Длительности и 💰 Цены
btn-plan-traffic = 🌐 Трафик
btn-plan-devices = 📱 Устройства
btn-plan-subscription-count = 🔢 Кол-во подписок
btn-plan-allowed = 👥 Разрешенные пользователи
btn-plan-squads = 🔗 Сквады
btn-plan-internal-squads = ⏺️ Внутренние сквады
btn-plan-external-squads = ⏹️ Внешний сквад
btn-allowed-user = { $id }
btn-plan-duration-add = 🆕 Добавить длительность
btn-plan-price-choice = 💸 { $price } { $currency }

btn-plan = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

btn-plan-active = { $is_active -> 
    [1] 🟢 Включен
    *[0] 🔴 Выключен
    }

btn-plan-type-choice = { $type -> 
    [TRAFFIC] 🌐 Трафик
    [DEVICES] 📱 Устройства
    [BOTH] 🔗 Трафик + устройства
    [UNLIMITED] ♾️ Безлимит
    *[OTHER] { $type }
    }

btn-plan-availability-choice = { $type -> 
    [ALL] 🌍 Для всех
    [NEW] 🌱 Для новых
    [EXISTING] 👥 Для клиентов
    [INVITED] ✉️ Для приглашенных
    [ALLOWED] 🔐 Для разрешенных
    [TRIAL] 🎁 Для пробника
    *[OTHER] { $type }
    }

btn-plan-traffic-strategy-choice = { $selected ->
    [1] 🔘 { traffic-strategy }
    *[0] ⚪ { traffic-strategy }
    }

btn-plan-duration = ⌛ { $value ->
    [-1] { unlimited }
    *[other] { unit-day }
    }


# RemnaWave
btn-remnawave-users = 👥 Пользователи
btn-remnawave-hosts = 🌐 Хосты
btn-remnawave-nodes = 🖥️ Ноды
btn-remnawave-inbounds = 🔌 Инбаунды


# Importer
btn-importer-from-xui = 💩 Импорт из панели 3X-UI
btn-importer-from-xui-shop = 🛒 Бот 3xui-shop
btn-importer-sync = 🌀 Запустить синхронизацию
btn-importer-squads = 🔗 Внутренние сквады
btn-importer-import-all = ✅ Импортировать всех
btn-importer-import-active = ❇️ Импортировать активных


# Subscription
btn-subscription-device-type = { $type ->
    [ANDROID] 📱 Android
    [IPHONE] 🍏 iPhone
    [WINDOWS] 🖥 Windows
    [MAC] 💻 Mac
    *[OTHER] { $type }
    }
btn-subscription-new = 💸 Купить подписку
btn-subscription-renew = 🔄 Продлить
btn-subscription-additional = 💠 Приобрести доп. подписку
btn-subscription-delete = ❌ Удалить
btn-subscription-confirm-delete = ❌ Точно удалить
btn-subscription-cancel-delete = ✅ Оставить
btn-subscription-my-subscriptions = 📋 Мои подписки ({ $count })
btn-subscription-item = { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $device_name } - { $expire_time }

btn-subscription-item-selectable = { $is_selected ->
    [1] ✅
    *[0] ⬜
    } { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $plan_name } - { $expire_time }

btn-subscription-confirm-selection = ✅ Продолжить ({ $count })
btn-subscription-continue-to-duration = ➡️ Выбрать длительность
btn-subscription-connect-url = 🔗 Получить ссылку
btn-subscription-copy-url = 📋 Скопировать ссылку
btn-subscription-promocode = 🎟 Активировать промокод
btn-subscription-payment-method = { gateway-type } | { $price } { $currency }
btn-subscription-pay = 💳 Оплатить
btn-subscription-get = 🎁 Получить бесплатно
btn-subscription-back-plans = ⬅️ Назад к выбору плана
btn-subscription-back-duration = ⬅️ Изменить длительность
btn-subscription-back-device-type = ⬅️ Изменить устройство
btn-subscription-back-payment-method = ⬅️ Изменить способ оплаты
btn-subscription-connect = 🚀 Подключиться
btn-subscription-duration = { $period } | { $final_amount ->
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }
btn-subscription-promocode-create-new = ➕ Создать новую подписку
btn-subscription-promocode-confirm-create = ✅ Создать
btn-subscription-privacy-policy = 📄 Политика конфиденциальности
btn-subscription-terms-of-service = 📋 Пользовательское соглашение


# Promocodes
btn-promocode-code = 🏷️ Код
btn-promocode-type = 🔖 Тип награды
btn-promocode-availability = ✴️ Доступ
btn-promocode-generate = 🎲 Сгенерировать код

btn-promocode-active = { $is_active ->
    [1] 🟢
    *[0] 🔴
    } Статус

btn-promocode-reward = 🎁 Награда
btn-promocode-lifetime = ⌛ Время жизни
btn-promocode-allowed = 👥 Лимит активаций
btn-promocode-confirm = ✅ Подтвердить

btn-promocode-type-choice = { $type ->
    [DURATION] ⏳ Дни подписки
    [TRAFFIC] 🌐 Трафик
    [DEVICES] 📱 Устройства
    [SUBSCRIPTION] 💳 Подписка
    [PERSONAL_DISCOUNT] 💸 Персональная скидка
    [PURCHASE_DISCOUNT] 🏷️ Скидка на покупку
    *[OTHER] { $type }
    }

btn-promocode-availability-choice = { $type ->
    [ALL] 🌍 Для всех
    [NEW] 🌱 Для новых
    [EXISTING] 👥 Для клиентов
    [INVITED] ✉️ Для приглашенных
    [ALLOWED] 🔐 Для разрешенных
    *[OTHER] { $type }
    }


# Partner Program (Admin)
btn-partner-enable = { $is_enabled ->
    [1] 🟢 Включена
    *[0] 🔴 Выключена
    }
btn-partner-level-percents = 📊 Проценты по уровням
btn-partner-level-percent = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } уровень: { $percent }%
btn-partner-tax-settings = 🏛 Налоги
btn-partner-tax-percent = 🏛 Налог ({ $percent }%)
btn-partner-gateway-fees = 💳 Комиссии ПС
btn-partner-gateway-fee = { gateway-type }: { $fee }%
btn-partner-min-withdrawal = ⬇️ Мин. вывод ({ $min_withdrawal })
btn-partner-level-choice = { $level ->
    [1] 1️⃣ Уровень 1
    [2] 2️⃣ Уровень 2
    [3] 3️⃣ Уровень 3
    *[OTHER] { $level } уровень
    }
btn-partner-withdrawals = 📝 Запросы ({ $count })
btn-partner-withdrawal-status = { $status ->
    [PENDING] 🕓 Ожидает
    [APPROVED] ✅ Одобрено
    [REJECTED] ❌ Отклонено
    *[OTHER] { $status }
    }
btn-partner-withdrawal-item = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [REJECTED] ❌
    *[OTHER] { $status }
    } { $user_id } - { $amount } - { $created_at }
btn-partner-withdrawal-approve = ✅ Выполнено
btn-partner-withdrawal-pending = 💭 На рассмотрении
btn-partner-withdrawal-reject = 🚫 Отказано

# Partner Program (Client)
btn-menu-partner = 👾 Партнерка
btn-partner-referrals = 👥 Мои рефералы ({ $count })
btn-partner-earnings = 📊 Мои начисления
btn-partner-withdraw = 💰 Вывод
btn-partner-withdraw-confirm = ✅ Подтвердить запрос
btn-partner-invite-copy = 🔗 Скопировать ссылку
btn-partner-invite-send = 📩 Пригласить
btn-partner-history = 📜 История выводов
btn-partner-referral-item = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } { $username } - { $total_earned }