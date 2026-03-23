# Remnashop
ntf-remnashop-info =
    <b>💎 Altshop v{ $version }</b>

    Данный проект основан на <a href="https://github.com/snoups/remnashop">Remnashop</a> от <b>snoups</b>. Поскольку бот полностью БЕСПЛАТНЫЙ и с открытым исходным кодом, он существует только благодаря вашей поддержке.

    ⭐ <i>Поставьте звездочку на <a href="https://github.com/dizzzable/altshop">GitHub</a> и поддержите <a href="https://github.com/snoups/remnashop">оригинального разработчика</a>.</i>


# Menu
msg-main-menu-body =
    { hdr-user-profile }
    { frg-user }

    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Срок действия истек.

    <i>Чтобы продлить, перейдите в меню «💳 Подписка»</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • Вы привысили лимит трафика.

    <i>Чтобы сбросить трафик, перейдите в меню «💳 Подписка»</i>
    </blockquote>
    [DISABLED]
    <blockquote>
    • Ваша подписка отключена.

    <i>Свяжитесь с техподдержкой для выяснения причины!</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • У вас нет оформленной подписки.

    <i>Для оформления перейдите в меню «💳 Подписка»</i>
    </blockquote>
    }

msg-main-menu = { msg-main-menu-body }
msg-main-menu-default = { msg-main-menu-body }
msg-main-menu-public = { msg-main-menu-body }

msg-menu-connect-device =
    <b>🚀 Выберите устройство для подключения</b>

    Выберите подписку, для которой хотите получить ссылку подключения.

msg-menu-connect-device-url =
    <b>🔗 Подключение</b>

    Нажмите кнопку ниже, чтобы перейти к подключению.

msg-menu-devices =
    <b>📱 Мои устройства</b>

    { $subscriptions_count ->
    [1] Выберите подписку для просмотра устройств.
    *[other] У вас <b>{ $subscriptions_count }</b> { $subscriptions_count ->
        [one] подписка
        [few] подписки
        *[other] подписок
        } с лимитом устройств. Выберите подписку для просмотра.
    }

msg-menu-devices-subscription =
    <b>📱 Устройства подписки #{ $subscription_index }</b>

    <blockquote>
    • <b>План</b>: { $plan_name }
    • <b>Устройств</b>: { $current_count } / { $max_count }
    </blockquote>

    { $devices_empty ->
    [1] <i>Нет привязанных устройств.</i>
    *[0] Здесь вы можете удалить привязанные устройства или получить ссылку подключения.
    }

msg-menu-invite =
    <b>👥 Пригласить друзей</b>
    
    Делитесь вашей уникальной ссылкой и получайте вознаграждение в виде { $reward_type ->
        [POINTS] <b>баллов, которые можно обменять на подписку или реальные деньги</b>
        [EXTRA_DAYS] <b>бесплатных дней к вашей подписке</b>
        *[OTHER] { $reward_type }
    }!

    <b>📊 Статистика:</b>
    <blockquote>
    👥 Всего приглашенных: { $referrals }
    💳 Платежей по вашей ссылке: { $payments }
    { $reward_type -> 
    [POINTS] 💎 Ваши баллы: { $points }
    *[EXTRA_DAYS] { empty }
    }
    </blockquote>

msg-menu-invite-about =
    <b>🎁 Подробнее о вознаграждении</b>

    <b>✨ Как получить награду:</b>
    <blockquote>
    { $accrual_strategy ->
    [ON_FIRST_PAYMENT] Награда начисляется за первую покупку подписки приглашенным пользователем.
    [ON_EACH_PAYMENT] Награда начисляется за каждую покупку или продление подписки приглашенным пользователем.
    *[OTHER] { $accrual_strategy }
    }
    </blockquote>

    <b>💎 Что вы получаете:</b>
    <blockquote>
    { $max_level -> 
    [1] За приглашенных друзей: { $reward_level_1 }
    *[MORE]
    { $identical_reward ->
    [0]
    1️⃣ За ваших друзей: { $reward_level_1 }
    2️⃣ За приглашенных вашими друзьями: { $reward_level_2 }
    *[1]
    За ваших друзей и приглашенных вашими друзьями: { $reward_level_1 }
    }
    }
    
    { $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }
        [EXTRA_DAYS] <i>(Все дополнительные дни начисляются к вашей текущей подписке)</i>
        *[OTHER] { $reward_type }
    }
    [PERCENT] { $reward_type ->
        [POINTS] <i>(Процент баллов от стоимости их приобретенной подписки)</i>
        [EXTRA_DAYS] <i>(Процент доп. дней от их приобретенной подписки)</i>
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    </blockquote>

msg-invite-reward = { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value ->
            [one] балл
            [few] балла
            *[more] баллов
            }
        [EXTRA_DAYS] { space }доп. { $value ->
            [one] день
            [few] дня
            *[more] дней
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] баллов
        [EXTRA_DAYS] доп. дней
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }

msg-menu-exchange =
    <b>🎁 Реферальные награды</b>

    Здесь вы можете обменять накопленные баллы на различные бонусы.

    <b>📊 Ваш баланс:</b>
    <blockquote>
    💎 Баллы: <b>{ $points }</b>
    </blockquote>

    <b>📈 Статистика:</b>
    <blockquote>
    👥 Приглашено друзей: { $referrals }
    💳 Платежей по вашей ссылке: { $payments }
    </blockquote>

    <b>🔄 Доступные типы обмена:</b>
    <blockquote>
    { $subscription_days_available ->
    [1] ⏳ Дни подписки: { $days_available } дней ({ $subscription_days_cost } балл = 1 день)
    *[0] { empty }
    }
    { $gift_subscription_available ->
    [1] 🎁 Подарочная подписка: { $gift_plan_name } на { $gift_duration_days } дней
    *[0] { empty }
    }
    { $discount_available ->
    [1] 💸 Скидка: до { $discount_percent }% ({ $discount_cost } баллов = 1%)
    *[0] { empty }
    }
    { $traffic_available ->
    [1] 🌐 Трафик: до { $traffic_gb } ГБ ({ $traffic_cost } баллов = 1 ГБ)
    *[0] { empty }
    }
    </blockquote>

    { $has_points ->
    [1] <i>Выберите тип обмена ниже.</i>
    *[0] <i>У вас пока нет баллов. Приглашайте друзей, чтобы получить награду!</i>
    }

msg-menu-exchange-select-type =
    <b>🔄 Выберите тип обмена</b>

    У вас <b>{ $points }</b> { $points ->
        [one] балл
        [few] балла
        *[other] баллов
    }.

    Выберите, на что хотите обменять баллы:

msg-menu-exchange-gift =
    <b>🎁 Обмен на подарочную подписку</b>

    Вы можете обменять баллы на промокод с подарочной подпиской для друга.

    <blockquote>
    • <b>Ваши баллы</b>: { $points }
    • <b>Стоимость</b>: { $cost } баллов
    • <b>Длительность</b>: { $duration_days } дней
    </blockquote>

    { $can_exchange ->
    [1] <i>Выберите план для подарочной подписки.</i>
    *[0] <i>У вас недостаточно баллов для обмена.</i>
    }

msg-menu-exchange-gift-select-plan =
    <b>📦 Выберите план для подарочной подписки</b>

    Выберите план, который получит ваш друг при активации промокода.

    <blockquote>
    • <b>Ваши баллы</b>: { $points }
    • <b>Стоимость</b>: { $cost } баллов
    </blockquote>

msg-menu-exchange-gift-confirm =
    <b>🎁 Подтверждение обмена</b>

    Вы собираетесь создать промокод на подарочную подписку:

    <blockquote>
    • <b>План</b>: { $plan_name }
    • <b>Длительность</b>: { $duration_days } дней
    • <b>Стоимость</b>: { $cost } баллов
    </blockquote>

    { $can_exchange ->
    [1] <i>Нажмите кнопку ниже, чтобы получить промокод.</i>
    *[0] <i>У вас недостаточно баллов для обмена.</i>
    }

msg-menu-exchange-gift-success =
    <b>🎉 Промокод создан!</b>

    Ваш промокод на подарочную подписку:

    <blockquote>
    <code>{ $promocode }</code>
    </blockquote>

    <b>Детали:</b>
    <blockquote>
    • <b>План</b>: { $plan_name }
    • <b>Длительность</b>: { $duration_days } дней
    </blockquote>

    <i>Скопируйте промокод и отправьте его другу. Промокод одноразовый!</i>

msg-menu-exchange-discount =
    <b>💸 Обмен на скидку</b>

    Вы можете обменять баллы на скидку для следующей покупки.

    <blockquote>
    • <b>Ваши баллы</b>: { $points }
    • <b>Курс</b>: { $cost_per_percent } баллов = 1% скидки
    • <b>Доступная скидка</b>: { $discount_percent }%
    • <b>Будет потрачено</b>: { $points_to_spend } баллов
    • <b>Максимальная скидка</b>: { $max_discount }%
    </blockquote>

    { $can_exchange ->
    [1] <i>Нажмите кнопку ниже, чтобы получить скидку.</i>
    *[0] <i>У вас недостаточно баллов для обмена.</i>
    }

msg-menu-exchange-traffic =
    <b>🌐 Обмен на трафик</b>

    Вы можете обменять баллы на дополнительный трафик.

    <blockquote>
    • <b>Ваши баллы</b>: { $points }
    • <b>Курс</b>: { $cost_per_gb } баллов = 1 ГБ
    • <b>Доступно трафика</b>: { $traffic_gb } ГБ
    • <b>Максимум</b>: { $max_traffic } ГБ
    </blockquote>

    Выберите подписку, к которой добавить трафик:

msg-menu-exchange-traffic-confirm =
    <b>🌐 Подтверждение обмена на трафик</b>

    Вы собираетесь обменять <b>{ $points_to_spend }</b> баллов на <b>{ $traffic_gb }</b> ГБ трафика.

    <blockquote>
    • <b>Подписка</b>: { $subscription_name }
    • <b>Текущий лимит</b>: { $current_traffic_limit }
    </blockquote>

    Нажмите «Подтвердить», чтобы завершить обмен.

exchange-type-days-value = { $days } { $days ->
    [one] день
    [few] дня
    *[other] дней
    }
exchange-type-gift-value = { $plan_name } на { $days } дней
exchange-type-discount-value = { $percent }% скидки
exchange-type-traffic-value = { $gb } ГБ трафика

msg-menu-exchange-points =
    <b>💎 Выберите подписку</b>

    У вас <b>{ $points }</b> { $points ->
        [one] балл
        [few] балла
        *[other] баллов
    }, что равно <b>{ $days_available }</b> { $days_available ->
        [one] дню
        [few] дням
        *[other] дням
    } подписки.

    Выберите подписку, к которой хотите добавить дни:

msg-menu-exchange-points-confirm =
    <b>💎 Подтверждение обмена</b>

    Вы собираетесь обменять <b>{ $points }</b> { $points ->
        [one] балл
        [few] балла
        *[other] баллов
    } на <b>{ $days_to_add }</b> { $days_to_add ->
        [one] день
        [few] дня
        *[other] дней
    } подписки.

    <blockquote>
    • <b>Подписка</b>: { $subscription_name }
    • <b>Текущий срок</b>: { $expire_time }
    </blockquote>

    Нажмите «Подтвердить обмен», чтобы завершить операцию.


# Dashboard
msg-dashboard-main = <b>🛠 Панель управления</b>
msg-users-main = <b>👥 Пользователи</b>
msg-broadcast-main = <b>📢 Рассылка</b>
msg-statistics-main = { $statistics }
    
msg-statistics-users =
    <b>👥 Статистика по пользователям</b>

    <blockquote>
    • <b>Всего</b>: { $total_users }
    • <b>Новые за день</b>: { $new_users_daily }
    • <b>Новые за неделю</b>: { $new_users_weekly }
    • <b>Новые за месяц</b>: { $new_users_monthly }

    • <b>С подпиской</b>: { $users_with_subscription }
    • <b>Без подписки</b>: { $users_without_subscription }
    • <b>С пробным периодом</b>: { $users_with_trial }

    • <b>Заблокированные</b>: { $blocked_users }
    • <b>Заблокировали бота</b>: { $bot_blocked_users }

    • <b>Конверсия пользователей → покупка</b>: { $user_conversion }%
    • <b>Конверсия пробников → подписка</b>: { $trial_conversion }%
    </blockquote>

msg-statistics-transactions =
    <b>🧾 Статистика по транзакциям</b>

    <blockquote>
    • <b>Всего транзакций</b>: { $total_transactions }
    • <b>Завершенных транзакций</b>: { $completed_transactions }
    • <b>Бесплатных транзакций</b>: { $free_transactions }
    { $popular_gateway ->
    [0] { empty }
    *[HAS] • <b>Популярная платежная система</b>: { $popular_gateway }
    }
    </blockquote>

    { $payment_gateways }

msg-statistics-subscriptions =
    <b>💳 Статистика по подпискам</b>

    <blockquote>
    • <b>Активные</b>: { $total_active_subscriptions }
    • <b>Истекшие</b>: { $total_expire_subscriptions }
    • <b>Пробные</b>: { $active_trial_subscriptions }
    • <b>Истекающие (7 дней)</b>: { $expiring_subscriptions }
    </blockquote>

    <blockquote>
    • <b>С безлимитом</b>: { $total_unlimited }
    • <b>С лимитом трафика</b>: { $total_traffic }
    • <b>С лимитом устройств</b>: { $total_devices }
    </blockquote>

msg-statistics-plans = 
    <b>📦 Статистика по планам</b>

    { $plans }

msg-statistics-promocodes =
    <b>🎁 Статистика по промокодам</b>

    <blockquote>
    • <b>Общее кол-во активаций</b>: { $total_promo_activations }
    • <b>Самый популярный промокод</b>: { $most_popular_promo ->
    [0] { unknown }
    *[HAS] { $most_popular_promo }
    }
    • <b>Выдано дней</b>: { $total_promo_days }
    • <b>Выдано трафика</b>: { $total_promo_days }
    • <b>Выдано подписок</b>: { $total_promo_subscriptions }
    • <b>Выдано личных скидок</b>: { $total_promo_personal_discounts }
    • <b>Выдано одноразовых скидок</b>: { $total_promo_purchase_discounts }
    </blockquote>

msg-statistics-referrals =
    <b>👪 Статистика по реферальной системе</b>
    
    <blockquote>
    • <b></b>:
    </blockquote>

msg-statistics-transactions-gateway =
    <b>{ gateway-type }:</b>
    <blockquote>
    • <b>Общий доход</b>: { $total_income }{ $currency }
    • <b>Доход за день</b>: { $daily_income }{ $currency }
    • <b>Доход за неделю</b>: { $weekly_income }{ $currency }
    • <b>Доход за месяц</b>: { $monthly_income }{ $currency }
    • <b>Средний чек</b>: { $average_check }{ $currency }
    • <b>Сумма скидок</b>: { $total_discounts }{ $currency }
    </blockquote>

msg-statistics-plan =
    <b>{ $plan_name }:</b> { $popular -> 
    [0] { space }
    *[HAS] (⭐)
    }
    <blockquote>
    • <b>Всего подписок</b>: { $total_subscriptions }
    • <b>Активных подписок</b>: { $active_subscriptions }
    • <b>Популярная длительность</b>: { $popular_duration }

    • <b>Общий доход</b>: 
    { $all_income }
    </blockquote>

msg-statistics-plan-income = { $income }{ $currency }
    


# Access
msg-access-main =
    <b>🔓 Режим доступа</b>
    
    <b>Статус</b>: { access-mode }.

msg-access-conditions =
    <b>⚙️ Условия доступа</b>

msg-access-rules =
    <b>✳️ Изменить ссылку на правила</b>

    Введите ссылку (в формате https://telegram.org/tos).

msg-access-channel =
    <b>❇️ Изменить ссылку на канал/группу</b>

    Если ваша группа не имеет @username, отправьте ID группы и ссылку-приглашение отдельными сообщениями.
    
    Если у вас публичный канал/группа, введите только @username.


# Broadcast
msg-broadcast-list = <b>📄 Список рассылок</b>
msg-broadcast-plan-select = <b>📦 Выберите план для рассылки</b>
msg-broadcast-send = <b>📢 Отправить рассылку ({ audience-type })</b>

    { $audience_count } { $audience_count ->
    [one] пользователю
    [few] пользователям
    *[more] пользователей
    } будет отправлена рассылка

    <blockquote>
    • <b>Кнопка промокода</b>: { $promocode_enabled ->
        [1] Включена
        *[0] Выключена
    }
    • <b>Промокод</b>: <code>{ $promocode_code }</code>
    </blockquote>

msg-broadcast-content =
    <b>✉️ Содержимое рассылки</b>

    Отправьте любое сообщение: текст, изображение или все вместе (поддерживается HTML).

msg-broadcast-buttons = <b>✳️ Кнопки рассылки</b>

msg-broadcast-promocode =
    <b>🎟 Промокод для рассылки</b>

    Отправьте промокод сообщением, чтобы добавить кнопку в рассылку.

    Текущий код: <code>{ $promocode_code }</code>

msg-broadcast-view =
    <b>📢 Рассылка</b>

    <blockquote>
    • <b>ID</b>: <code>{ $broadcast_id }</code>
    • <b>Статус</b>: { broadcast-status }
    • <b>Аудитория</b>: { audience-type }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    <blockquote>
    • <b>Всего сообщений</b>: { $total_count }
    • <b>Успешных</b>: { $success_count }
    • <b>Неудачных</b>: { $failed_count }
    </blockquote>


# Users
msg-users-recent-registered = <b>🆕 Последние зарегистрированные</b>
msg-users-recent-activity = <b>📝 Последние взаимодействующие</b>
msg-user-transactions = <b>🧾 Транзакции пользователя</b>
msg-user-devices = <b>📱 Устройства пользователя ({ $current_count } / { $max_count })</b>
msg-user-give-access = <b>🔑 Предоставить доступ к плану</b>

msg-users-search =
    <b>🔍 Поиск пользователя</b>

    Введите ID пользователя, часть имени или перешлите любое его сообщение.

msg-users-search-results =
    <b>🔍 Поиск пользователя</b>

    Найдено <b>{ $count }</b> { $count ->
    [one] пользователь
    [few] пользователя
    *[more] пользователей
    }, { $count ->
    [one] соответствующий
    *[more] соответствующих
    } запросу

msg-user-main = 
    <b>📝 Информация о пользователе</b>

    { hdr-user-profile }
    { frg-user-details }

    <b>💸 Скидка:</b>
    <blockquote>
    • <b>Персональная</b>: { $personal_discount }%
    • <b>На следующую покупку</b>: { $purchase_discount }%
    </blockquote>
    
    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Срок действия истек.
    </blockquote>
    [LIMITED]
    <blockquote>
    • Превышен лимит трафика.
    </blockquote>
    [DISABLED]
    <blockquote>
    • Подписка отключена.
    </blockquote>
    *[NONE]
    <blockquote>
    • Нет текущей подписки.
    </blockquote>
    }

msg-user-give-subscription =
    <b>🎁 Выдать подписку</b>

    Выберите план, который хотите выдать пользователю.

msg-user-subscriptions =
    <b>📋 Подписки пользователя ({ $count })</b>

    Выберите подписку, которую хотите посмотреть или изменить.
    ⭐ отмечена текущая подписка пользователя.

msg-user-give-subscription-duration =
    <b>⏳ Выберите длительность</b>

    Выберите длительность выдаваемой подписки.

msg-user-discount =
    <b>💸 Изменить персональную скидку</b>

    Выберите по кнопке или введите свой вариант.

msg-user-purchase-discount =
    <b>🛒 Изменить скидку на следующую покупку</b>

    Выберите по кнопке или введите свой вариант (0-100).

msg-user-points =
    <b>💎 Изменить баллы реферальной системы</b>

    <b>Текущее кол-во баллов: { $current_points }</b>

    Выберите по кнопке или введите свой вариант, чтобы добавить или отнять.

msg-user-subscription-traffic-limit =
    <b>🌐 Изменить лимит трафика</b>

    Выберите по кнопке или введите свой вариант (в ГБ), чтобы изменить лимит трафика.

msg-user-subscription-device-limit =
    <b>📱 Изменить лимит устройств</b>

    Выберите по кнопке или введите свой вариант, чтобы изменить лимит устройств.

msg-user-subscription-expire-time =
    <b>⏳ Изменить срок действия</b>

    <b>Закончится через: { $expire_time }</b>

    Выберите по кнопке или введите свой вариант (в днях), чтобы добавить или отнять.

msg-user-subscription-squads =
    <b>🔗 Изменить список сквадов</b>

    { $internal_squads ->
    [0] { empty }
    *[HAS] <b>⏺️ Внутренние:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { empty }
    *[HAS] <b>⏹️ Внешний:</b> { $external_squad }
    }

msg-user-subscription-internal-squads =
    <b>⏺️ Изменить список внутренних сквадов</b>

    Выберите, какие внутренние группы будут присвоены этому пользователю.

msg-user-subscription-external-squads =
    <b>⏹️ Изменить внешний сквад</b>

    Выберите, какая внешняя группа будет присвоена этому пользователю.

msg-user-subscription-info =
    <b>💳 Информация о подписке</b>

    <blockquote>
    • <b>Выбрана</b>: { $subscription_index } / { $subscriptions_count }
    • <b>Текущая</b>: { $is_current_subscription ->
    [1] Да
    *[0] Нет
    }
    </blockquote>
    
    { hdr-subscription }
    { frg-subscription-details }

    <blockquote>
    • <b>Сквады</b>: { $squads -> 
    [0] { unknown }
    *[HAS] { $squads }
    }
    • <b>Первое подключение</b>: { $first_connected_at -> 
    [0] { unknown }
    *[HAS] { $first_connected_at }
    }
    • <b>Последнее подключение</b>: { $last_connected_at ->
    [0] { unknown }
    *[HAS] { $last_connected_at } ({ $node_name })
    } 
    </blockquote>

    { hdr-plan }
    { frg-plan-snapshot }

msg-user-transaction-info =
    <b>🧾 Информация о транзакции</b>

    { hdr-payment }
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Тип</b>: { purchase-type }
    • <b>Статус</b>: { transaction-status }
    • <b>Способ оплаты</b>: { gateway-type }
    • <b>Сумма</b>: { frg-payment-amount }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    { $is_test -> 
    [1] ⚠️ Тестовая транзакция
    *[0]
    { hdr-plan }
    { frg-plan-snapshot }
    }
    
msg-user-role = 
    <b>👮‍♂️ Изменить роль</b>
    
    Выберите новую роль для пользователя.

msg-users-blacklist =
    <b>🚫 Черный список</b>

    Заблокировано: <b>{ $count_blocked }</b> / <b>{ $count_users }</b> ({ $percent }%).

msg-user-message =
    <b>📩 Отправить сообщение пользователю</b>

    Отправьте любое сообщение: текст, изображение или все вместе (поддерживается HTML).
    

# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave</b>
    
    <b>🖥️ Система:</b>
    <blockquote>
    • <b>ЦПУ</b>: { $cpu_cores } { $cpu_cores ->
    [one] ядро
    [few] ядра
    *[more] ядер
    } { $cpu_threads } { $cpu_threads ->
    [one] поток
    [few] потока
    *[more] потоков
    }
    • <b>ОЗУ</b>: { $ram_used } / { $ram_total } ({ $ram_used_percent }%)
    • <b>Аптайм</b>: { $uptime }
    </blockquote>

msg-remnawave-users =
    <b>👥 Пользователи</b>

    <b>📊 Статистика:</b>
    <blockquote>
    • <b>Всего</b>: { $users_total }
    • <b>Активные</b>: { $users_active }
    • <b>Отключенные</b>: { $users_disabled }
    • <b>Ограниченные</b>: { $users_limited }
    • <b>Истекшие</b>: { $users_expired }
    </blockquote>

    <b>🟢 Онлайн:</b>
    <blockquote>
    • <b>За день</b>: { $online_last_day }
    • <b>За неделю</b>: { $online_last_week }
    • <b>Никогда не заходили</b>: { $online_never }
    • <b>Сейчас онлайн</b>: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    <b>{ $remark } ({ $status ->
    [ON] включен
    *[OFF] выключен
    }):</b>
    <blockquote>
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    { $inbound_uuid ->
    [0] { empty }
    *[HAS] • <b>Инбаунд</b>: <code>{ $inbound_uuid }</code>
    }
    </blockquote>

msg-remnawave-node-details =
    <b>{ $country } { $name } ({ $status ->
    [ON] подключено
    *[OFF] отключено
    }):</b>
    <blockquote>
    • <b>Адрес</b>: <code>{ $address }{ $port -> 
    [0] { empty }
    *[HAS]:{ $port }
    }</code>
    • <b>Аптайм (xray)</b>: { $xray_uptime }
    • <b>Пользователей онлайн</b>: { $users_online }
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-inbound-details =
    <b>🔗 { $tag }</b>
    <blockquote>
    • <b>ID</b>: <code>{ $inbound_id }</code>
    • <b>Протокол</b>: { $type } ({ $network })
    { $port ->
    [0] { empty }
    *[HAS] • <b>Порт</b>: { $port }
    }
    { $security ->
    [0] { empty }
    *[HAS] • <b>Безопасность</b>: { $security } 
    }
    </blockquote>

msg-remnawave-hosts =
    <b>🌐 Хосты</b>
    
    { $host }

msg-remnawave-nodes = 
    <b>🖥️ Ноды</b>

    { $node }

msg-remnawave-inbounds =
    <b>🔌 Инбаунды</b>

    { $inbound }


# RemnaShop
msg-remnashop-main = <b>🛍 { $project_name }</b>
msg-admins-main = <b>👮‍♂️ Администраторы</b>


# Multi Subscription
msg-multi-subscription-main =
    <b>📦 Мультиподписка</b>

    <blockquote>
    • <b>Статус</b>: { $is_enabled ->
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    • <b>Макс. подписок по умолчанию</b>: { $default_max ->
        [-1] ∞ Без ограничений
        *[other] { $default_max }
        }
    </blockquote>

    <i>Когда мультиподписка выключена, пользователи могут иметь только одну подписку.
    Индивидуальный лимит можно настроить для каждого пользователя отдельно.</i>

msg-multi-subscription-max =
    <b>🔢 Макс. количество подписок</b>

    <blockquote>
    Текущее значение: { $default_max ->
        [-1] <b>∞ Без ограничений</b>
        *[other] <b>{ $default_max }</b>
        }
    </blockquote>

    Введите максимальное количество подписок, которое пользователь может приобрести.
    Введите -1 для снятия ограничения.

msg-user-max-subscriptions =
    <b>📦 Индивидуальный лимит подписок</b>

    <blockquote>
    • <b>Режим</b>: { $use_global ->
        [1] 🌐 Глобальные настройки
        *[0] ⚙️ Индивидуальные настройки
        }
    • <b>Текущий лимит</b>: { $current_max ->
        [-1] ∞ Без ограничений
        *[other] { $current_max }
        }
    { $use_global ->
    [0] { empty }
    *[1] • <b>Глобальный лимит</b>: { $global_max ->
        [-1] ∞ Без ограничений
        *[other] { $global_max }
        }
    }
    </blockquote>

    { $use_global ->
    [1] <i>Пользователь использует глобальные настройки. Нажмите кнопку ниже чтобы установить индивидуальный лимит.</i>
    *[0] <i>Выберите лимит из списка или введите свой вариант.
    Введите -1 для снятия ограничения.</i>
    }


# Banners
msg-banners-main =
    <b>🖼️ Управление баннерами</b>

    Здесь вы можете загружать и удалять баннеры для различных разделов бота.

    <blockquote>
    Поддерживаемые форматы: JPG, JPEG, PNG, GIF, WEBP
    </blockquote>

    Выберите баннер для редактирования:

msg-banner-select =
    <b>🖼️ Баннер: { $banner_display_name }</b>

    { $has_banner ->
    [1] <blockquote>
    ✅ Баннер загружен для локали <b>{ $locale }</b>
    </blockquote>
    *[0] <blockquote>
    ❌ Баннер не загружен для локали <b>{ $locale }</b>
    </blockquote>
    }

    Выберите локаль и действие:

msg-banner-upload =
    <b>📤 Загрузка баннера</b>

    <blockquote>
    • <b>Баннер</b>: { $banner_display_name }
    • <b>Локаль</b>: { $locale }
    </blockquote>

    Отправьте изображение для загрузки.

    <i>Поддерживаемые форматы: { $supported_formats }</i>

msg-banner-confirm-delete =
    <b>⚠️ Подтверждение удаления</b>

    Вы уверены, что хотите удалить баннер?

    <blockquote>
    • <b>Баннер</b>: { $banner_display_name }
    • <b>Локаль</b>: { $locale }
    </blockquote>

    <i>Это действие нельзя отменить.</i>


# Gateways
msg-gateways-main = <b>🌐 Платежные системы</b>
msg-gateways-settings = <b>🌐 Конфигурация { gateway-type }</b>
msg-gateways-default-currency = <b>💸 Валюта по умолчанию</b>
msg-gateways-placement = <b>🔢 Изменить позиционирование</b>

msg-gateways-field =
    <b>🌐 Конфигурация { gateway-type }</b>

    Введите новое значение для { $field }.


# Referral
msg-referral-main =
    <b>👥 Реферальная система</b>

    <blockquote>
    • <b>Статус</b>: { $is_enable ->
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    • <b>Тип награды</b>: { reward-type }
    • <b>Количество уровней</b>: { $referral_level }
    • <b>Условие начисления</b>: { accrual-strategy }
    • <b>Форма начисления</b>: { reward-strategy }
    • <b>Тарифы для наград</b>: { $has_plan_filter ->
        [1] { $eligible_plans_count } { $eligible_plans_count ->
            [one] тариф
            [few] тарифа
            *[other] тарифов
            }
        *[0] Все тарифы
        }
    </blockquote>

    Выберите пункт для изменения.

msg-referral-level =
    <b>🔢 Изменить уровень</b>

    Выберите максимальный уровень реферала.

msg-referral-reward-type =
    <b>🎀 Изменить тип награды</b>

    Выберите новый тип награды.
    
msg-referral-accrual-strategy =
    <b>📍 Изменить условие начисления</b>

    Выберите, в каком случае будет начисляться награда.


msg-referral-reward-strategy =
    <b>⚖️ Изменить форму начисления</b>

    Выберите способ расчета награды.


msg-referral-reward-level = { $level } уровень: { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value -> 
            [one] балл
            [few] балла
            *[more] баллов
            }
        [EXTRA_DAYS] { space }доп. { $value -> 
            [one] день
            [few] дня
            *[more] дней
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] баллов
        [EXTRA_DAYS] доп. дней
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    
msg-referral-reward =
    <b>🎁 Изменить награду</b>

    <blockquote>
    { $reward }
    </blockquote>

    { $reward_strategy_type ->
        [AMOUNT] Введите количество { $reward_type ->
            [POINTS] баллов
            [EXTRA_DAYS] дней
            *[OTHER] { $reward_type }
        }
        [PERCENT] Введите процент от { $reward_type ->
            [POINTS] <u>стоимости подписки</u>
            [EXTRA_DAYS] <u>длительности подписки</u>
            *[OTHER] { $reward_type }
        }
        *[OTHER] { $reward_strategy_type }
    } (в формате: уровень=значение)

msg-referral-eligible-plans =
    <b>📦 Тарифы для начисления наград</b>

    { $has_filter ->
    [1] Выбрано <b>{ $eligible_count }</b> { $eligible_count ->
        [one] тариф
        [few] тарифа
        *[other] тарифов
        }. Награды начисляются только за покупку выбранных тарифов.
    *[0] Фильтр не установлен. Награды начисляются за покупку <b>любого</b> тарифа.
    }

    Выберите тарифы, за покупку которых будут начисляться реферальные награды.

msg-referral-points-exchange =
    <b>💎 Настройки обмена баллов</b>

    <blockquote>
    • <b>Статус</b>: { $exchange_enabled ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    • <b>Типов обмена включено</b>: { $enabled_types_count }
    • <b>Курс обмена (дни)</b>: { $points_per_day } { $points_per_day ->
        [one] балл
        [few] балла
        *[other] баллов
        } = 1 день
    • <b>Мин. баллов для обмена</b>: { $min_exchange_points }
    • <b>Макс. баллов за обмен</b>: { $max_exchange_points ->
        [-1] Без ограничений
        *[other] { $max_exchange_points }
        }
    </blockquote>

    Выберите параметр для изменения.

msg-referral-exchange-types =
    <b>🔄 Типы обмена баллов</b>

    Выберите тип обмена для настройки. Включенные типы будут доступны пользователям.

msg-referral-exchange-type-settings =
    <b>⚙️ Настройки типа обмена</b>

    <blockquote>
    • <b>Тип</b>: { $exchange_type ->
        [SUBSCRIPTION_DAYS] ⏳ Дни подписки
        [GIFT_SUBSCRIPTION] 🎁 Подарочная подписка
        [DISCOUNT] 💸 Скидка на покупку
        [TRAFFIC] 🌐 Дополнительный трафик
        *[OTHER] { $exchange_type }
        }
    • <b>Статус</b>: { $enabled ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    • <b>Стоимость</b>: { $points_cost } { $points_cost ->
        [one] балл
        [few] балла
        *[other] баллов
        } { $exchange_type ->
        [SUBSCRIPTION_DAYS] = 1 день
        [GIFT_SUBSCRIPTION] = 1 промокод
        [DISCOUNT] = 1% скидки
        [TRAFFIC] = 1 ГБ
        *[OTHER] { empty }
        }
    • <b>Мин. баллов</b>: { $min_points }
    • <b>Макс. баллов</b>: { $max_points ->
        [-1] Без ограничений
        *[other] { $max_points }
        }
    { $exchange_type ->
    [GIFT_SUBSCRIPTION]
    • <b>План</b>: { $gift_plan_name }
    • <b>Длительность</b>: { $gift_duration_days } дней
    [DISCOUNT]
    • <b>Макс. скидка</b>: { $max_discount_percent }%
    [TRAFFIC]
    • <b>Макс. трафик</b>: { $max_traffic_gb } ГБ
    *[OTHER] { empty }
    }
    </blockquote>

    Выберите параметр для изменения.

msg-referral-exchange-type-cost =
    <b>💰 Стоимость в баллах</b>

    <blockquote>
    Текущая стоимость: <b>{ $points_cost }</b> { $points_cost ->
        [one] балл
        [few] балла
        *[other] баллов
        }
    </blockquote>

    Введите количество баллов за единицу { $exchange_type ->
        [SUBSCRIPTION_DAYS] (1 день подписки)
        [GIFT_SUBSCRIPTION] (1 промокод)
        [DISCOUNT] (1% скидки)
        [TRAFFIC] (1 ГБ трафика)
        *[OTHER] { empty }
        }.

msg-referral-exchange-type-min =
    <b>⬇️ Минимальное количество баллов</b>

    <blockquote>
    Текущее значение: <b>{ $min_points }</b>
    </blockquote>

    Введите минимальное количество баллов для этого типа обмена.

msg-referral-exchange-type-max =
    <b>⬆️ Максимальное количество баллов</b>

    <blockquote>
    Текущее значение: { $max_points ->
        [-1] <b>Без ограничений</b>
        *[other] <b>{ $max_points }</b>
        }
    </blockquote>

    Введите максимальное количество баллов за один обмен.
    Введите -1 для снятия ограничения.

msg-referral-gift-plan =
    <b>📦 План для подарочной подписки</b>

    Выберите план, который будет выдаваться при обмене баллов на подарочную подписку.

msg-referral-gift-duration =
    <b>⏳ Длительность подарочной подписки</b>

    <blockquote>
    Текущая длительность: <b>{ $gift_duration_days }</b> дней
    </blockquote>

    Введите количество дней для подарочной подписки.

msg-referral-discount-max =
    <b>💸 Максимальный процент скидки</b>

    <blockquote>
    Текущее значение: <b>{ $max_discount_percent }%</b>
    </blockquote>

    Введите максимальный процент скидки (1-100).

msg-referral-traffic-max =
    <b>🌐 Максимальное количество трафика</b>

    <blockquote>
    Текущее значение: <b>{ $max_traffic_gb } ГБ</b>
    </blockquote>

    Введите максимальное количество ГБ трафика.

exchange-type-subscription-days-desc = Обмен баллов на дополнительные дни подписки
exchange-type-gift-subscription-desc = Промокод на подписку ({ $plan_name }, { $days } дней)
exchange-type-discount-desc = Скидка на следующую покупку (до { $max_percent }%)
exchange-type-traffic-desc = Дополнительный трафик (до { $max_gb } ГБ)

msg-referral-points-per-day =
    <b>📊 Изменить курс обмена</b>

    <blockquote>
    Текущий курс: <b>{ $points_per_day }</b> { $points_per_day ->
        [one] балл
        [few] балла
        *[other] баллов
        } = 1 день подписки
    </blockquote>

    Введите количество баллов, необходимых для получения 1 дня подписки.

msg-referral-min-exchange-points =
    <b>⬇️ Минимальное количество баллов для обмена</b>

    <blockquote>
    Текущее значение: <b>{ $min_exchange_points }</b>
    </blockquote>

    Введите минимальное количество баллов, которое пользователь должен накопить для обмена.

msg-referral-max-exchange-points =
    <b>⬆️ Максимальное количество баллов за один обмен</b>

    <blockquote>
    Текущее значение: { $max_exchange_points ->
        [-1] <b>Без ограничений</b>
        *[other] <b>{ $max_exchange_points }</b>
        }
    </blockquote>

    Введите максимальное количество баллов, которое можно обменять за один раз.
    Введите -1 для снятия ограничения.

# Plans
msg-plans-main = <b>📦 Планы</b>

msg-plan-configurator =
    <b>📦 Конфигуратор плана</b>

    <blockquote>
    • <b>Название</b>: { $name }
    • <b>Тип</b>: { plan-type }
    • <b>Доступ</b>: { availability-type }
    • <b>Статус</b>: { $is_active ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    </blockquote>
    
    <blockquote>
    • <b>Лимит трафика</b>: { $is_unlimited_traffic ->
        [1] { unlimited }
        *[0] { $traffic_limit }
        }
    • <b>Лимит устройств</b>: { $is_unlimited_devices ->
        [1] { unlimited }
        *[0] { $device_limit }
        }
    </blockquote>

    Выберите пункт для изменения.

msg-plan-name =
    <b>🏷️ Изменить название</b>

    { $name ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $name }
    </blockquote>
    }

    Введите новое название плана.

msg-plan-description =
    <b>💬 Изменить описание</b>

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    Введите новое описание плана.

msg-plan-tag =
    <b>📌 Изменить тег</b>

    { $tag ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $tag }
    </blockquote>
    }

    Введите новой тег плана (только латинские заглавные буквы, цифры и символ подчеркивания).

msg-plan-type =
    <b>🔖 Изменить тип</b>

    Выберите новый тип плана.

msg-plan-availability =
    <b>✴️ Изменить доступность</b>

    Выберите доступность плана.

msg-plan-traffic =
    <b>🌐 Изменить лимит и стратегию сброса трафика</b>

    Введите новый лимит трафика плана (в ГБ) и выберите стратегию его сброса.

msg-plan-devices =
    <b>📱 Изменить лимит устройств</b>

    Введите новый лимит устройств плана.

msg-plan-subscription-count =
    <b>🔢 Изменить количество подписок</b>

    Введите количество подписок, которые пользователь получит при покупке этого плана.
    
    <i>Например: 1 - одна подписка, 3 - три подписки и т.д.</i>

msg-plan-durations =
    <b>⏳ Длительности плана</b>

    Выберите длительность для изменения цены.

msg-plan-duration =
    <b>⏳ Добавить длительность плана</b>

    Введите новую длительность (в днях).

msg-plan-prices =
    <b>💰 Изменить цены длительности ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Выберите валюту с ценой для изменения.

msg-plan-price =
    <b>💰 Изменить цену для длительности ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Введите новую цену для валюты { $currency }.

msg-plan-allowed-users = 
    <b>👥 Изменить список разрешенных пользователей</b>

    Введите ID пользователя для добавления в список.

msg-plan-squads =
    <b>🔗 Сквады</b>

    { $internal_squads ->
    [0] { empty }
    *[HAS] <b>⏺️ Внутренние:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { empty }
    *[HAS] <b>⏹️ Внешний:</b> { $external_squad }
    }

msg-plan-internal-squads =
    <b>⏺️ Изменить список внутренних сквадов</b>

    Выберите, какие внутренние группы будут присвоены этому плану.

msg-plan-external-squads =
    <b>⏹️ Изменить внешний сквад</b>

    Выберите, какая внешняя группа будет присвоена этому плану.


# Notifications
msg-notifications-main = <b>🔔 Настройка уведомлений</b>
msg-notifications-user = <b>👥 Пользовательские уведомления</b>
msg-notifications-system = <b>⚙️ Системные уведомления</b>


# Subscription
msg-subscription-main = <b>💳 Подписка</b>

    { $subscriptions_count ->
    [0] <blockquote>У вас нет активных подписок.</blockquote>
    [1] <blockquote>У вас <b>1</b> подписка.</blockquote>
    *[other] <blockquote>У вас <b>{ $subscriptions_count }</b> { $subscriptions_count ->
        [one] подписка
        [few] подписки
        *[other] подписок
        }.</blockquote>
    }

msg-subscription-my-subscriptions =
    <b>📋 Мои подписки</b>

    Выберите подписку для просмотра деталей и получения ссылки подключения.

msg-subscription-details-view =
    <b>💳 Подписка #{ $subscription_index }</b>

    <blockquote>
    • Статус: { $status ->
        [ACTIVE] 🟢 Активна
        [EXPIRED] 🔴 Истекла
        [LIMITED] 🟡 Лимит исчерпан
        [DISABLED] ⚫ Отключена
        *[OTHER] { $status }
        }
    • План: { $plan_name }
    • Лимит трафика: { $traffic_limit }
    • Лимит устройств: { $device_limit }
    • Оплачено: { $paid_at }
    • Действует до: { $expire_time }
    • Устройство: { $device_type ->
        [0] не указано
        [ANDROID] 📱 Android
        [IPHONE] 🍏 iPhone
        [WINDOWS] 🖥 Windows
        [MAC] 💻 Mac
        *[OTHER] { $device_type }
        }
    </blockquote>

msg-subscription-confirm-delete =
    <b>⚠️ Подтверждение удаления</b>

    Вы уверены, что хотите удалить подписку <b>#{ $subscription_index }</b>?

    <blockquote>
    • <b>План</b>: { $plan_name }
    • <b>Истекает</b>: { $expire_time }
    </blockquote>

    <i>Это действие нельзя отменить. Подписка будет удалена из панели и базы данных.</i>

msg-subscription-device-type =
    <b>📱 Выберите устройство{ $is_multiple ->
    [1] { space }({ $current_index } из { $total_count })
    *[0] { empty }
    }</b>

    На каком устройстве вы будете использовать { $is_multiple ->
    [1] эту подписку?
    *[0] подписку?
    }

msg-subscription-select-for-renew =
    <b>🔄 Выберите подписку для продления</b>

    У вас несколько подписок. Выберите, какую хотите продлить.

msg-subscription-select-for-renew-single =
    <b>🔄 Выберите подписку для продления</b>

    У вас несколько подписок. Выберите одну подписку, которую хотите продлить.

msg-subscription-select-for-renew-multi =
    <b>🔄 Выберите подписки для продления</b>

    Выберите одну или несколько подписок, которые хотите продлить.
    { $selected_count ->
    [0] <i>Ничего не выбрано</i>
    [1] <i>Выбрана 1 подписка</i>
    [2] <i>Выбрано 2 подписки</i>
    [3] <i>Выбрано 3 подписки</i>
    [4] <i>Выбрано 4 подписки</i>
    *[other] <i>Выбрано { $selected_count } подписок</i>
    }

msg-subscription-confirm-renew-selection =
    <b>✅ Подтверждение выбора</b>

    Вы выбрали <b>{ $selected_count }</b> { $selected_count ->
    [1] подписку
    [2] подписки
    [3] подписки
    [4] подписки
    *[other] подписок
    } для продления.

    <blockquote>
    { $has_discount ->
    [1] • <b>Стоимость</b>: <s>{ $total_original_price }{ $currency }</s> <b>{ $final_amount }{ $currency }</b> (−{ $discount_percent }%)
    *[0] • <b>Стоимость</b>: <b>{ $final_amount }{ $currency }</b>
    }
    </blockquote>

    Нажмите «Продолжить» для выбора длительности.

msg-subscription-plans = <b>📦 Выберите план</b>
msg-subscription-new-success = Чтобы начать пользоваться нашим сервисом, нажмите кнопку <code>`{ btn-subscription-connect }`</code> и следуйте инструкциям!
msg-subscription-renew-success = Ваша подписка продлена на { $added_duration }.

msg-subscription-details =
    <b>{ $plan }:</b>
    <blockquote>
    { $description ->
    [0] { empty }
    *[HAS]
    { $description }
    }

    • <b>Лимит трафика</b>: { $traffic }
    • <b>Лимит устройств</b>: { $devices }
    { $subscription_count ->
    [1] { empty }
    *[HAS] • <b>Кол-во подписок</b>: { $subscription_count }
    }
    { $period ->
    [0] { empty }
    *[HAS] • <b>Длительность</b>: { $period }
    }
    { $final_amount ->
    [0] { empty }
    *[HAS] • <b>Стоимость</b>: { frg-payment-amount }
    }
    </blockquote>

msg-subscription-duration = 
    <b>⏳ Выберите длительность</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 Выберите способ оплаты</b>

    { msg-subscription-details }

msg-subscription-confirm =
    { $purchase_type ->
    [RENEW] <b>🛒 Подтверждение продления подписки</b>
    [ADDITIONAL] <b>🛒 Подтверждение покупки доп. подписки</b>
    *[OTHER] <b>🛒 Подтверждение покупки подписки</b>
    }

    { msg-subscription-details }

    { $purchase_type ->
    [RENEW] <i>⚠️ Текущая подписка будет <u>продлена</u> на выбранный срок.</i>
    [ADDITIONAL] <i>💠 Будет создана дополнительная подписка для нового устройства.</i>
    *[OTHER] { empty }
    }

msg-subscription-trial =
    <b>✅ Пробная подписка успешно получена!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ Оплата прошла успешно!</b>

    { $purchase_type ->
    [NEW] { msg-subscription-new-success }
    [RENEW] { msg-subscription-renew-success }
    [ADDITIONAL] { msg-subscription-additional-success }
    *[OTHER] { $purchase_type }
    }

msg-subscription-additional-success =
    Дополнительная подписка успешно создана!

    <b>{ $plan_name }</b>
    { frg-subscription }
    
    <i>Теперь вы можете использовать эту подписку на новом устройстве.</i>

msg-subscription-failed = 
    <b>❌ Произошла ошибка!</b>

    Не волнуйтесь, техподдержка уже уведомлена и свяжется с вами в ближайшее время. Приносим извинения за неудобства.


# Importer
msg-importer-main =
    <b>📥 Импорт пользователей</b>

    Запуск синхронизации: проверка всех пользователей в RemnaWave. Если пользователя нет в базе бота, он будет создан и получит временную подписку. Если данные пользователя отличаются, они будут автоматически обновлены.

msg-importer-from-xui =
    <b>📥 Импорт пользователей (3X-UI)</b>
    
    { $has_exported -> 
    [1]
    <b>🔍 Найдено:</b>
    <blockquote>
    Всего пользователей: { $total }
    С активной подпиской: { $active }
    С истекшей подпиской: { $expired }
    </blockquote>
    *[0]
    Импортируются все активные пользователи с числовым email.

    Рекомендуется заранее отключить пользователей, у которых в поле email отсутствует Telegram ID. Операция может занять значительное время в зависимости от количества пользователей.

    Отправьте файл базы данных (в формате .db).
    }

msg-importer-squads =
    <b>🔗 Список внутренних сквадов</b>

    Выберите, какие внутренние группы будут доступны импортированным пользователям.

msg-importer-import-completed =
    <b>📥 Импорт пользователей завершен</b>
    
    <b>📃 Информация:</b>
    <blockquote>
    • <b>Всего пользователей</b>: { $total_count }
    • <b>Успешно импортированы</b>: { $success_count }
    • <b>Не удалось импортировать</b>: { $failed_count }
    </blockquote>

msg-importer-sync-completed =
    <b>📥 Синхронизация пользователей завершена</b>

    <b>📃 Информация:</b>
    <blockquote>
    Всего пользователей в панели: { $total_panel_users }
    Всего пользователей в боте: { $total_bot_users }

    Новые пользователи: { $added_users }
    Добавлены подписки: { $added_subscription }
    Обновлены подписки: { $updated}
    
    Пользователи без Telegram ID: { $missing_telegram }
    Ошибки при синхронизации: { $errors }
    </blockquote>


# Promocodes
msg-promocodes-main = <b>🎟 Промокоды</b>
msg-promocodes-list = <b>📃 Список промокодов</b>

msg-promocode-configurator =
    <b>🎟 Конфигуратор промокода</b>

    <blockquote>
    • <b>Код</b>: { $code }
    • <b>Тип</b>: { promocode-type }
    • <b>Доступ</b>: { availability-type }
    • <b>Статус</b>: { $is_active ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    </blockquote>

    <blockquote>
    { $promocode_type ->
    [DURATION] • <b>Длительность</b>: { $reward }
    [TRAFFIC] • <b>Трафик</b>: { $reward }
    [DEVICES] • <b>Устройства</b>: { $reward }
    [SUBSCRIPTION] • <b>Подписка</b>: { frg-plan-snapshot }
    [PERSONAL_DISCOUNT] • <b>Персональная скидка</b>: { $reward }%
    [PURCHASE_DISCOUNT] • <b>Скидка на покупку</b>: { $reward }%
    *[OTHER] { $promocode_type }
    }
    • <b>Срок действия</b>: { $lifetime }
    • <b>Лимит активаций</b>: { $max_activations }
    </blockquote>

    Выберите пункт для изменения.

msg-promocode-code =
    <b>🏷️ Код промокода</b>

    Введите код промокода или нажмите кнопку для генерации случайного кода.

msg-promocode-type =
    <b>🔖 Тип награды</b>

    Выберите тип награды промокода.

msg-promocode-availability =
    <b>✴️ Доступность промокода</b>

    Выберите, кому будет доступен промокод.

msg-promocode-reward =
    <b>🎁 Награда промокода</b>

    { $reward_type ->
    [DURATION] Введите количество дней.
    [TRAFFIC] Введите количество ГБ трафика.
    [DEVICES] Введите количество устройств.
    [PERSONAL_DISCOUNT] Введите процент персональной скидки (1-100).
    [PURCHASE_DISCOUNT] Введите процент скидки на покупку (1-100).
    *[OTHER] Введите значение награды.
    }

msg-promocode-lifetime =
    <b>⌛ Срок действия</b>

    Введите количество дней действия промокода.
    Введите -1 для бессрочного промокода.

msg-promocode-allowed =
    <b>👥 Лимит активаций</b>

    Введите максимальное количество активаций.
    Введите -1 для безлимитного промокода.

msg-promocode-activation-limit =
    <b>👥 Лимит активаций</b>

    Введите максимальное количество активаций.
    Введите -1 для безлимитного промокода.

msg-promocode-plan-filter =
    <b>📋 Фильтр планов промокода</b>

    Выберите планы, к которым можно применять этот промокод.
    Если список пустой, промокод действует на все планы.

msg-promocode-allowed-users =
    <b>🔐 Разрешенные пользователи</b>

    Отправьте Telegram ID, username или часть имени для поиска.
    Найденный пользователь будет добавлен в список разрешенных для этого промокода.

msg-promocode-allowed-users-search-results =
    <b>🔎 Найдено пользователей: { $count }</b>

    Выберите пользователя для добавления в список разрешенных.

msg-subscription-promocode =
    <b>🎟 Активация промокода</b>

    Введите код промокода для активации.

msg-subscription-promocode-select =
    <b>🎟 Выбор подписки для промокода</b>

    У вас есть активные подписки. Выберите, к какой подписке добавить <b>{ $promocode_days }</b> { $promocode_days ->
    [1] день
    [2] дня
    [3] дня
    [4] дня
    *[other] дней
    }.

    Или создайте новую подписку.

msg-subscription-promocode-select-duration =
    <b>🎟 Выбор подписки для начисления дней</b>

    У вас несколько активных подписок. Выберите, к какой подписке добавить <b>{ $promocode_days }</b> { $promocode_days ->
    [1] день
    [2] дня
    [3] дня
    [4] дня
    *[other] дней
    } от промокода.

msg-subscription-promocode-confirm-new =
    <b>🎟 Создание новой подписки</b>

    Вы собираетесь создать новую подписку по промокоду:

    <blockquote>
    • <b>План</b>: { $plan_name }
    • <b>Длительность</b>: { $days_formatted }
    </blockquote>

    Нажмите «Создать», чтобы подтвердить.

msg-promocode-plan =
    <b>📦 Выберите план для промокода</b>

    Выберите план, который будет выдан при активации промокода.

msg-promocode-duration =
    <b>⏳ Выберите длительность</b>

    Выберите длительность подписки для плана <b>{ $plan_name }</b>.


# Partner Program (Admin Settings)
msg-partner-admin-main =
    <b>👾 Партнерская программа</b>

    <blockquote>
    • <b>Статус</b>: { $is_enabled ->
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    • <b>Проценты по уровням</b>:
      1️⃣ { $level1_percent }%
      2️⃣ { $level2_percent }%
      3️⃣ { $level3_percent }%
    • <b>Налог</b>: { $tax_percent }%
    • <b>Мин. вывод</b>: { $min_withdrawal }
    </blockquote>

    <b>💳 Комиссии платежных систем:</b>
    <blockquote>
    { $gateway_fees }
    </blockquote>

    Выберите пункт для изменения.

msg-partner-level-percents =
    <b>📊 Проценты по уровням</b>

    <blockquote>
    1️⃣ Уровень 1: { $level1_percent }%
    2️⃣ Уровень 2: { $level2_percent }%
    3️⃣ Уровень 3: { $level3_percent }%
    </blockquote>

    Введите новое значение в формате: <code>уровень=процент</code>
    Например: <code>1=10</code> для 10% на 1 уровне.

msg-partner-level-percent-edit =
    <b>📊 Редактирование процента уровня { $level }</b>

    <blockquote>
    Текущий процент: <b>{ $current_percent }%</b>
    </blockquote>

    Введите новый процент (0-100).

msg-partner-tax-settings =
    <b>🏛 Настройки налогов</b>

    <blockquote>
    Текущий налог: <b>{ $tax_percent }%</b>
    </blockquote>

    Введите процент налога (0-100).
    Этот процент будет вычитаться из начисления партнера.

msg-partner-gateway-fees =
    <b>💳 Комиссии платежных систем</b>

    Выберите платежную систему для изменения комиссии.

msg-partner-gateway-fee-edit =
    <b>💳 Комиссия { gateway-type }</b>

    <blockquote>
    Текущая комиссия: <b>{ $current_fee }%</b>
    </blockquote>

    Введите процент комиссии платежной системы (0-100).

msg-partner-min-withdrawal =
    <b>⬇️ Минимальная сумма вывода</b>

    <blockquote>
    Текущее значение: <b>{ $min_withdrawal }</b>
    </blockquote>

    Введите минимальную сумму для вывода средств.

msg-partner-withdrawals =
    <b>💸 Заявки на вывод</b>

    { $count ->
    [0] <i>Нет заявок на вывод.</i>
    [1] <b>1</b> заявка ожидает рассмотрения.
    *[other] <b>{ $count }</b> заявок ожидает рассмотрения.
    }

msg-partner-withdrawals-list =
    <b>📝 Запросы на вывод</b>

    Список запросов на вывод от партнеров. Выберите запрос для просмотра деталей и обработки.

msg-partner-withdrawal-details =
    <b>📝 Детали запроса на вывод</b>

    <blockquote>
    • <b>ID партнера</b>: <code>{ $partner_telegram_id }</code>
    • <b>Сумма</b>: { $amount_rubles } руб.
    • <b>Статус</b>: { $status ->
        [PENDING] 🕓 Ожидает
        [COMPLETED] ✅ Выполнено
        [REJECTED] 🚫 Отказано
        *[OTHER] { $status }
        }
    • <b>Создано</b>: { $created_at }
    { $processed_at ->
        [0] { empty }
        *[HAS] • <b>Обработано</b>: { $processed_at }
    }
    { $payment_details ->
        [Не указаны] { empty }
        *[HAS] • <b>Реквизиты</b>: { $payment_details }
    }
    </blockquote>

    Выберите действие для обработки запроса:

msg-partner-withdrawal-view =
    <b>💸 Заявка на вывод</b>

    <blockquote>
    • <b>ID</b>: <code>{ $withdrawal_id }</code>
    • <b>Партнер</b>: { $partner_user_id }
    • <b>Сумма</b>: { $amount }
    • <b>Статус</b>: { $status ->
        [PENDING] 🕓 Ожидает
        [APPROVED] ✅ Одобрено
        [REJECTED] ❌ Отклонено
        *[OTHER] { $status }
        }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    { $status ->
    [PENDING] Выберите действие:
    *[OTHER] { empty }
    }

# Partner Program (User Edit in Admin)
msg-user-partner =
    <b>👾 Партнерка пользователя</b>

    { $is_partner ->
    [1]
    <blockquote>
    • <b>Статус</b>: { $is_active ->
        [1] 🟢 Активна
        *[0] 🔴 Неактивна
        }
    • <b>Баланс</b>: { $balance }
    • <b>Всего заработано</b>: { $total_earned }
    • <b>Приглашено рефералов</b>: { $referrals_count }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    <b>📊 Начисления по уровням:</b>
    <blockquote>
    1️⃣ { $level1_earned } ({ $level1_count } рефералов)
    2️⃣ { $level2_earned } ({ $level2_count } рефералов)
    3️⃣ { $level3_earned } ({ $level3_count } рефералов)
    </blockquote>
    *[0]
    <blockquote>
    У пользователя нет партнерки.
    </blockquote>

    <i>Выдайте партнерку, чтобы пользователь мог приглашать рефералов и получать % с их оплат.</i>
    }

msg-user-partner-balance =
    <b>💰 Изменить баланс партнера</b>

    <b>Текущий баланс: { $current_balance }</b>

    Выберите по кнопке или введите свой вариант (в рублях), чтобы добавить или отнять.

msg-user-partner-withdrawals =
    <b>💸 Заявки на вывод пользователя</b>

    { $count ->
    [0] <i>Нет заявок на вывод.</i>
    [1] <b>1</b> заявка.
    *[other] <b>{ $count }</b> заявок.
    }

msg-user-partner-settings =
    <b>⚙️ Индивидуальные настройки партнера</b>

    <blockquote>
    • <b>Режим</b>: { $use_global ->
        [1] 🌐 Глобальные настройки
        *[0] ⚙️ Индивидуальные настройки
        }
    { $use_global ->
    [1] { empty }
    *[0]
    • <b>Условие начисления</b>: { $accrual_strategy ->
        [ON_FIRST_PAYMENT] 💳 Только первый платеж
        [ON_EACH_PAYMENT] 💸 Каждый платеж
        *[OTHER] { $accrual_strategy }
        }
    • <b>Тип награды</b>: { $reward_type ->
        [PERCENT] 📊 Процент от оплаты
        [FIXED_AMOUNT] 💰 Фиксированная сумма
        *[OTHER] { $reward_type }
        }
    { $reward_type ->
    [PERCENT]
    • <b>Проценты по уровням</b>:
      1️⃣ { $level1_percent }%
      2️⃣ { $level2_percent }%
      3️⃣ { $level3_percent }%
    [FIXED_AMOUNT]
    • <b>Фиксированные суммы</b>:
      1️⃣ { $level1_fixed } руб.
      2️⃣ { $level2_fixed } руб.
      3️⃣ { $level3_fixed } руб.
    *[OTHER] { empty }
    }
    }
    </blockquote>

    Выберите параметр для изменения.

msg-user-partner-accrual-strategy =
    <b>📍 Условие начисления партнеру</b>

    Выберите, когда партнер будет получать вознаграждение за реферала:

    <blockquote>
    • <b>Только первый платеж</b> — партнер получит награду только за первую оплату реферала
    • <b>Каждый платеж</b> — партнер будет получать награду с каждой оплаты реферала
    </blockquote>

msg-user-partner-reward-type =
    <b>🎀 Тип награды партнера</b>

    Выберите, как рассчитывается награда партнера:

    <blockquote>
    • <b>Процент от оплаты</b> — процент от суммы платежа реферала
    • <b>Фиксированная сумма</b> — фиксированное вознаграждение за каждый платеж
    </blockquote>

msg-user-partner-percent =
    <b>📊 Проценты по уровням</b>

    <blockquote>
    Текущие значения:
    1️⃣ Уровень 1: { $current_level1 }%
    2️⃣ Уровень 2: { $current_level2 }%
    3️⃣ Уровень 3: { $current_level3 }%

    Глобальные настройки:
    1️⃣ { $global_level1 }% | 2️⃣ { $global_level2 }% | 3️⃣ { $global_level3 }%
    </blockquote>

    Выберите процент для каждого уровня ниже или введите вручную в формате: <code>уровень процент</code>
    Например: <code>1 15</code> — установит 15% для 1 уровня.

msg-user-partner-percent-level1 =
    <b>1️⃣ Уровень 1</b> (текущий: { $current_level1 }%)

msg-user-partner-percent-level2 =
    <b>2️⃣ Уровень 2</b> (текущий: { $current_level2 }%)

msg-user-partner-percent-level3 =
    <b>3️⃣ Уровень 3</b> (текущий: { $current_level3 }%)

msg-user-partner-percent-edit =
    <b>📊 Редактирование процента уровня { $level }</b>

    <blockquote>
    Текущий процент: <b>{ $current_percent }%</b>
    </blockquote>

    Введите новый процент (0-100).

msg-user-partner-fixed =
    <b>💰 Фиксированные суммы по уровням</b>

    <blockquote>
    Текущие значения:
    1️⃣ Уровень 1: { $current_level1 } руб.
    2️⃣ Уровень 2: { $current_level2 } руб.
    3️⃣ Уровень 3: { $current_level3 } руб.
    </blockquote>

    Выберите сумму для каждого уровня ниже или введите вручную в формате: <code>уровень сумма</code>
    Например: <code>1 150</code> — установит 150 руб. для 1 уровня.

msg-user-partner-fixed-level1 =
    <b>1️⃣ Уровень 1</b> (текущий: { $current_level1 } руб.)

msg-user-partner-fixed-level2 =
    <b>2️⃣ Уровень 2</b> (текущий: { $current_level2 } руб.)

msg-user-partner-fixed-level3 =
    <b>3️⃣ Уровень 3</b> (текущий: { $current_level3 } руб.)

msg-user-partner-fixed-edit =
    <b>💰 Редактирование суммы уровня { $level }</b>

    <blockquote>
    Текущая сумма: <b>{ $current_amount } руб.</b>
    </blockquote>

    Введите новую сумму (в рублях).

# Partner Program (Client Interface)
msg-partner-main =
    <b>👾 Партнерская программа</b>

    Приглашайте друзей и получайте процент с каждой их оплаты!

    <b>💰 Ваш баланс:</b>
    <blockquote>
    • <b>Доступно к выводу</b>: { $balance }
    • <b>Всего заработано</b>: { $total_earned }
    • <b>Выведено</b>: { $total_withdrawn }
    </blockquote>

    <b>👥 Ваши рефералы:</b>
    <blockquote>
    • 1️⃣ уровень: { $level1_count } (заработано: { $level1_earned })
    • 2️⃣ уровень: { $level2_count } (заработано: { $level2_earned })
    • 3️⃣ уровень: { $level3_count } (заработано: { $level3_earned })
    </blockquote>

    <b>📊 Ваши проценты:</b>
    <blockquote>
    • 1️⃣ уровень: { $level1_percent }%
    • 2️⃣ уровень: { $level2_percent }%
    • 3️⃣ уровень: { $level3_percent }%
    </blockquote>

msg-partner-balance-currency =
    <b>💱 Валюта партнерского баланса</b>

    <blockquote>
    • <b>Текущая настройка</b>: { $current_currency }
    • <b>Фактически используется</b>: { $effective_currency }
    </blockquote>

    Выберите валюту отображения баланса и сумм вывода.
    Для XTR автоматически используется RUB.

msg-partner-referrals =
    <b>👥 Мои рефералы</b>

    { $count ->
    [0] <i>У вас пока нет рефералов. Поделитесь ссылкой с друзьями!</i>
    [1] У вас <b>1</b> реферал.
    *[other] У вас <b>{ $count }</b> рефералов.
    }

msg-partner-earnings =
    <b>📊 История начислений</b>

    { $count ->
    [0] <i>У вас пока нет начислений.</i>
    *[other] Последние начисления:
    }

msg-partner-earning-item =
    <blockquote>
    • <b>Сумма</b>: +{ $amount }
    • <b>Уровень</b>: { $level ->
        [1] 1️⃣
        [2] 2️⃣
        [3] 3️⃣
        *[OTHER] { $level }
        }
    • <b>От реферала</b>: { $referral_id }
    • <b>Дата</b>: { $created_at }
    </blockquote>

msg-partner-withdraw =
    <b>💸 Вывод средств</b>

    <blockquote>
    • <b>Доступно к выводу</b>: { $balance }
    • <b>Минимальная сумма</b>: { $min_withdrawal }
    </blockquote>

    { $can_withdraw ->
    [1] Введите сумму для вывода или нажмите кнопку для вывода всех средств.
    *[0] <i>Недостаточно средств для вывода. Минимальная сумма: { $min_withdrawal }</i>
    }

msg-partner-withdraw-confirm =
    <b>📝 Подтверждение запроса на вывод</b>

    <blockquote>
    • <b>Сумма</b>: { $amount }
    • <b>Комиссия</b>: { $fee } ({ $fee_percent }%)
    • <b>К получению</b>: { $net_amount }
    </blockquote>

    <i>⚠️ После подтверждения ваш запрос будет отправлен на рассмотрение администратору. Средства будут переведены после одобрения.</i>

msg-partner-withdraw-success =
    <b>✅ Заявка на вывод создана</b>

    Ваша заявка на вывод <b>{ $amount }</b> отправлена на рассмотрение.
    Администратор свяжется с вами для уточнения деталей.

msg-partner-history =
    <b>📜 История выводов</b>

    { $count ->
    [0] <i>У вас пока нет выводов.</i>
    *[other] Ваши заявки на вывод:
    }

msg-partner-history-item =
    <blockquote>
    • <b>Сумма</b>: { $amount }
    • <b>Статус</b>: { $status ->
        [PENDING] 🕓 Ожидает
        [APPROVED] ✅ Одобрено
        [REJECTED] ❌ Отклонено
        *[OTHER] { $status }
        }
    • <b>Дата</b>: { $created_at }
    </blockquote>

msg-partner-invite =
    <b>🔗 Пригласите друзей</b>

    Поделитесь ссылкой с друзьями и получайте { $level1_percent }% с каждой их оплаты!

    Ваша партнерская ссылка:
    <code>{ $invite_link }</code>

msg-partner-net-earning-info =
    <b>💰 Расчет начисления</b>

    <blockquote>
    • <b>Сумма оплаты</b>: { $payment_amount }
    • <b>Комиссия ПС</b>: -{ $gateway_fee } ({ $gateway_fee_percent }%)
    • <b>Налог</b>: -{ $tax } ({ $tax_percent }%)
    • <b>Чистая сумма</b>: { $net_amount }
    • <b>Ваш процент</b>: { $partner_percent }%
    • <b>Ваше начисление</b>: <b>+{ $partner_earning }</b>
    </blockquote>


# Backup System
msg-backup-main =
    <b>💾 Система бэкапов</b>

    <blockquote>
    • <b>Автобэкап</b>: { $auto_enabled ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    { $auto_enabled ->
    [1]
    • <b>Интервал</b>: каждые { $interval_hours } ч.
    • <b>Время</b>: { $backup_time }
    *[0] { empty }
    }
    • <b>Сохранять бэкапов</b>: { $max_keep }
    • <b>Сжатие</b>: { $compression ->
        [1] 🟢 Включено
        *[0] 🔴 Выключено
        }
    • <b>Отправка в Telegram</b>: { $send_enabled ->
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    </blockquote>

    <i>Создавайте резервные копии базы данных и отправляйте их в Telegram.</i>

msg-backup-list =
    <b>📦 Список бэкапов</b>

    { $has_backups ->
    [1] Найдено <b>{ $total_backups }</b> { $total_backups ->
        [one] бэкап
        [few] бэкапа
        *[other] бэкапов
        }.
    *[0] <i>Бэкапы отсутствуют.</i>
    }

msg-backup-manage =
    <b>📦 Управление бэкапом</b>

    { $found ->
    [1]
    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Размер</b>: { $file_size_mb } МБ
    • <b>Создан</b>: { $timestamp }
    • <b>Записей</b>: { $total_records }
    </blockquote>

    <b>📊 Содержимое:</b>
    <blockquote>
    { $content_details }
    </blockquote>
    *[0]
    <blockquote>
    ❌ Бэкап не найден или поврежден.
    </blockquote>
    }

msg-backup-settings =
    <b>⚙️ Настройки бэкапов</b>

    <blockquote>
    • <b>Автобэкап</b>: { $auto_enabled ->
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    • <b>Интервал</b>: каждые { $interval_hours } ч.
    • <b>Время</b>: { $backup_time }
    • <b>Макс. бэкапов</b>: { $max_keep }
    • <b>Сжатие</b>: { $compression ->
        [1] 🟢 Да
        *[0] 🔴 Нет
        }
    • <b>Отправка в Telegram</b>: { $send_enabled ->
        [1] 🟢 Да (чат: { $send_chat_id })
        *[0] 🔴 Нет
        }
    </blockquote>

    <i>Настройки бэкапов задаются через переменные окружения.</i>

msg-backup-restore-confirm =
    <b>⚠️ Подтверждение восстановления</b>

    Вы собираетесь восстановить базу данных из бэкапа:

    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Создан</b>: { $timestamp }
    • <b>Записей</b>: { $total_records }
    { $clear_before ->
    [1]
    
    ⚠️ <b>ВНИМАНИЕ</b>: Текущие данные будут УДАЛЕНЫ перед восстановлением!
    *[0]
    
    ℹ️ Текущие данные будут ОБЪЕДИНЕНЫ с данными из бэкапа.
    }
    </blockquote>

    <b>Это действие нельзя отменить!</b> Продолжить?

msg-backup-delete-confirm =
    <b>⚠️ Подтверждение удаления</b>

    Вы собираетесь удалить бэкап:

    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Создан</b>: { $timestamp }
    </blockquote>

    <b>Это действие нельзя отменить!</b> Продолжить?

msg-backup-created =
    <b>✅ Бэкап успешно создан!</b>

    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Размер</b>: { $file_size_mb } МБ
    • <b>Записей</b>: { $total_records }
    </blockquote>

msg-backup-restored =
    <b>✅ База данных успешно восстановлена!</b>

    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Восстановлено записей</b>: { $restored_records }
    </blockquote>

msg-backup-deleted =
    <b>✅ Бэкап успешно удален!</b>

msg-backup-error =
    <b>❌ Ошибка!</b>

    { $error_message }

msg-backup-content-item = • <b>{ $table_name }</b>: { $count }

# Importer plan assignment
msg-importer-assign-plan =
    <b>Назначение плана после синхронизации</b>

    <blockquote>
    Пользователей из последней синхронизации: { $synced_users_count }
    </blockquote>

    Выберите активный план и подтвердите массовое назначение.

# User plan assignment
msg-user-assign-plan =
    <b>Назначить план пользователю</b>

    <blockquote>
    Текущий план: { $current_plan_name }
    </blockquote>

    Выберите активный план. Он будет применен к выбранной подписке пользователя.

msg-user-assign-plan-subscriptions =
    <b>📋 Выберите подписку для назначения плана ({ $count })</b>

    Сначала выберите, для какой подписки пользователя нужно поменять план.
    ⭐ отмечена текущая подписка пользователя.

msg-menu-invite-referrals =
    <b>👥 Мои рефералы</b>

    { $count ->
    [0] <i>У вас пока нет приглашенных пользователей.</i>
    [one] У вас <b>1</b> приглашенный пользователь.
    [few] У вас <b>{ $count }</b> приглашенных пользователя.
    *[other] У вас <b>{ $count }</b> приглашенных пользователей.
    }

msg-users-referrals =
    <b>👥 Все приглашенные пользователи</b>

    Найдено записей: <b>{ $count }</b>.

msg-user-referrals =
    <b>👥 Приглашенные этим пользователем</b>

    Найдено записей: <b>{ $count }</b>.

msg-branding-main =
    <b>🎨 Настройки брендинга</b>

    <blockquote>
    • <b>Название проекта</b>: { $project_name }
    • <b>Web title</b>: { $web_title }
    • <b>Текст кнопки меню бота</b>: { $bot_menu_button_text }
    </blockquote>

    <b>Превью Telegram верификации (RU):</b>
    <blockquote><code>{ $tg_preview_ru }</code></blockquote>

    <b>Превью Telegram верификации (EN):</b>
    <blockquote><code>{ $tg_preview_en }</code></blockquote>

    <b>Превью Telegram сброса пароля (RU):</b>
    <blockquote><code>{ $password_reset_tg_preview_ru }</code></blockquote>

    <b>Превью Telegram сброса пароля (EN):</b>
    <blockquote><code>{ $password_reset_tg_preview_en }</code></blockquote>

    <b>Превью web-сообщений:</b>
    <blockquote>
    • Отправлено (RU): <code>{ $web_request_delivered_ru }</code>
    • Отправлено (EN): <code>{ $web_request_delivered_en }</code>
    • Открыть бота (RU): <code>{ $web_request_open_bot_ru }</code>
    • Открыть бота (EN): <code>{ $web_request_open_bot_en }</code>
    • Успешное подтверждение (RU): <code>{ $web_confirm_success_ru }</code>
    • Успешное подтверждение (EN): <code>{ $web_confirm_success_en }</code>
    </blockquote>

    <i>Выберите поле кнопкой ниже и отправьте новое значение следующим сообщением.</i>

msg-branding-edit =
    <b>✏️ Редактирование поля брендинга</b>

    <blockquote>
    • <b>Поле</b>: { $field_label }
    • <b>Текущее значение</b>:
    <code>{ $current_value }</code>
    </blockquote>

    Отправьте новое значение следующим сообщением.
msg-subscription-payment-asset =
    <b>Выберите монету оплаты</b>

    { msg-subscription-details }
msg-plan-archived-renew-mode =
    <b>🔁 Режим продления архивного тарифа</b>

    <b>Продлевать этот же тариф</b>:
    пользователь сможет оплачивать и продлевать архивный тариф без замены.

    <b>Заменять при продлении</b>:
    сам архивный тариф больше нельзя продлить напрямую, при оплате он будет
    заменен на один из тарифов из списка "Замены при продлении".

msg-plan-replacement-plans =
    <b>🔄 Тарифы для замены при продлении</b>

    Отметьте публичные тарифы, которые можно предложить пользователю,
    когда архивный тариф больше нельзя продлевать как есть.

    Пользователь увидит только эти варианты, а после оплаты старая подписка
    будет переведена на новый тариф с его текущими настройками.

msg-plan-upgrade-plans =
    <b>⬆️ Тарифы для улучшения</b>

    Отметьте тарифы, на которые разрешено улучшение именно из этого тарифа.

    Это не общий список всех доступных планов: пользователь сможет перейти
    только на отмеченные здесь варианты.

msg-plan-configurator-transitions =
    <i>{ $is_archived ->
    [1] 🗃️ Архивный тариф скрыт из обычной витрины. { $renew_mode ->
        [SELF_RENEW] Его можно продлевать как есть.
        [REPLACE_ON_RENEW] При продлении он заменится на один из { $replacement_count } выбранных тарифов.
        *[other] Режим продления настроен отдельно.
        }
    *[0] 🛒 Публичный тариф доступен к покупке новым пользователям.
    } ⬆️ Улучшений из этого тарифа настроено: { $upgrade_count }.</i>
msg-main-menu-invite-locked =
    <b>🔒 Доступ ограничен приглашением</b>

    Бот уже открыт, но продуктовые разделы пока заблокированы.
    Получите новую invite-ссылку от пригласившего вас пользователя и откройте бота по ней.

    Доступны только безопасные действия: правила, язык и поддержка.
msg-menu-invite-status-title = <b>Статус ссылки приглашения</b>
msg-menu-invite-status-active = ✅ Ссылка активна и готова к отправке.
msg-menu-invite-status-expired = ⌛ Срок действия ссылки истёк. Сгенерируйте новую ссылку.
msg-menu-invite-status-exhausted = 🚫 Свободные слоты приглашений закончились.
msg-menu-invite-status-missing = ⚠️ Активная ссылка пока недоступна.
msg-menu-invite-status-never = бессрочно
msg-menu-invite-status-expires-at = ⏰ Работает до: { $expires_at }
msg-menu-invite-status-slots = 👥 Слоты: { $remaining } из { $total }
msg-menu-invite-status-slots-unlimited = 👥 Слоты: без ограничений
msg-menu-invite-status-progress = 📈 До следующего расширения: { $current } / { $target }
msg-menu-invite-status-progress-disabled = 📈 Автодобавление слотов отключено
msg-referral-invite-limits =
    <b>🎟 Ограничения invite-ссылок</b>

    <blockquote>
    • Срок действия ссылки: { $ttl_enabled ->
        [true] включен
        *[false] выключен
        }
    • Время жизни: { $ttl_value }
    • Лимит приглашений: { $slots_enabled ->
        [true] включен
        *[false] выключен
        }
    • Стартовые слоты: { $initial_slots }
    • Порог квалификаций: { $refill_threshold }
    • Добавлять слотов: { $refill_amount }
    </blockquote>

    Если срок жизни включен, пользователь должен перевыпускать ссылку после истечения.
    Если лимит слотов включен, новые приглашения доступны только в рамках свободной ёмкости.
msg-referral-invite-ttl =
    <b>⌛ Время жизни invite-ссылки</b>

    Отправьте число в секундах.
    <blockquote>
    • 900 = 15 минут
    • 14400 = 4 часа
    • 604800 = 7 дней
    • 0 = бессрочно
    </blockquote>
msg-referral-invite-initial-slots =
    <b>1️⃣ Стартовые слоты приглашений</b>

    Отправьте, сколько пользователей можно пригласить сразу.
    <blockquote>0 = без стартовых слотов</blockquote>
msg-referral-invite-refill-threshold =
    <b>📈 Порог квалификаций</b>

    Отправьте, сколько квалифицированных рефералов нужно для автоматического добавления новых слотов.
    <blockquote>0 = автодобавление выключено</blockquote>
msg-referral-invite-refill-amount =
    <b>➕ Количество новых слотов</b>

    Отправьте, сколько слотов добавлять после каждого достигнутого порога квалификаций.
    <blockquote>0 = новые слоты не добавляются</blockquote>
msg-referral-invite-unset = не задано
msg-referral-invite-enabled-status = { $enabled ->
    [true] включено
    *[false] выключено
    }
msg-user-referral-invite-settings =
    <b>🎟 Индивидуальные настройки invite-ссылок</b>

    Здесь можно обойти глобальные правила для выбранного пользователя и задать отдельные TTL и лимиты приглашений.
msg-user-referral-invite-settings-summary =
    <blockquote>
    • Эффективный TTL: { $effective_ttl_enabled }, значение: { $effective_ttl_value }
    • Эффективный лимит слотов: { $effective_slots_enabled }
    • Стартовые слоты: { $effective_initial_slots }
    • Порог квалификаций: { $effective_refill_threshold }
    • Добавлять слотов: { $effective_refill_amount }
    </blockquote>
