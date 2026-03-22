# Errors
ntf-error = <i>❌ Произошла ошибка. Попробуйте позже.</i>
ntf-error-lost-context = <i>⚠️ Произошла ошибка. Диалог перезапущен.</i>
ntf-error-log-not-found = <i>⚠️ Ошибка: Лог файл не найден.</i>

# Exchange notifications
ntf-exchange-points-no-points = ❌ У вас недостаточно баллов для обмена.
ntf-exchange-points-disabled = ❌ Обмен баллов временно отключен.
ntf-exchange-points-min = ❌ Минимальное количество баллов для обмена: { $min_points }
ntf-exchange-points-success = ✅ Успешно! Вы обменяли { $points } баллов на { $days } дней подписки.
ntf-exchange-gift-no-plan = ❌ План для подарочной подписки не настроен. Обратитесь к администратору.
ntf-exchange-gift-success = ✅ Промокод создан! Код: { $promocode }
ntf-exchange-discount-success = ✅ Успешно! Вы получили скидку { $discount }% на следующую покупку. Потрачено { $points } баллов.
ntf-exchange-traffic-success = ✅ Успешно! Вы добавили { $traffic } ГБ трафика. Потрачено { $points } баллов.
ntf-points-exchange-invalid-value = ❌ Введите корректное положительное число.
ntf-points-exchange-invalid-percent = ❌ Введите корректный процент (1-100).


# Events
ntf-event-error =
    #EventError

    <b>🔅 Событие: Произошла ошибка!</b>

    { $user -> 
    [1]
    { hdr-user }
    { frg-user-info }
    *[0] { space }
    }

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-error-remnawave =
    #EventError

    <b>🔅 Событие: Ошибка при подключении к Remnawave!</b>

    <blockquote>
    Без активного подключения корректная работа бота невозможна!
    </blockquote>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-error-webhook =
    #EventError

    <b>🔅 Событие: Зафиксирована ошибка вебхука!</b>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-bot-startup =
    #EventBotStarted

    <b>🔅 Событие: Бот запущен!</b>

    <blockquote>
    • <b>Режим доступа</b>: { access-mode }
    </blockquote>

ntf-event-bot-shutdown =
    #EventBotShutdown

    <b>🔅 Событие: Бот остановлен!</b>

ntf-event-bot-update =
    #EventBotUpdate

    <b>🔅 Событие: Обнаружено обновление Remnashop!</b>

    <blockquote>
    • <b>Текущая версия</b>: { $local_version }
    • <b>Доступная версия</b>: { $remote_version }
    </blockquote>

ntf-event-new-user =
    #EventNewUser

    <b>🔅 Событие: Новый пользователь!</b>

    { hdr-user }
    { frg-user-info }

    { $has_referrer ->
    [0] { empty }
    *[HAS]
    <b>🤝 Реферер:</b>
    <blockquote>
    • <b>ID</b>: <code>{ $referrer_user_id }</code>
    • <b>Имя</b>: { $referrer_user_name } { $referrer_username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $referrer_user_id }">@{ $referrer_username }</a>)
    }
    </blockquote>
    }
    
ntf-event-subscription-trial =
    #EventTrialGetted

    <b>🔅 Событие: Получение пробной подписки!</b>

    { hdr-user }
    { frg-user-info }
    
    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-new =
    #EventSubscriptionNew

    <b>🔅 Событие: Покупка подписки!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-renew =
    #EventSubscriptionRenew

    <b>🔅 Событие: Продление подписки!</b>
    
    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-additional =
    #EventSubscriptionAdditional

    <b>🔅 Событие: Покупка дополнительной подписки!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-node-connection-lost =
    #EventNode

    <b>🔅 Событие: Соединение с узлом потеряно!</b>

    { hdr-node }
    { frg-node-info }

ntf-event-node-connection-restored =
    #EventNode

    <b>🔅 Событие: Cоединение с узлом восстановлено!</b>

    { hdr-node }
    { frg-node-info }

ntf-event-node-traffic =
    #EventNode

    <b>🔅 Событие: Узел достиг порога лимита трафика!</b>

    { hdr-node }
    { frg-node-info }

# ntf-event-user-sync =
#     #EventUser

#     <b>🔅 Событие: Синхронизация пользователя!</b>

#     { hdr-user }
#     { frg-user-info }

#     { hdr-subscription }
#     { frg-subscription-details }

# ntf-event-user-deleted =
#     #EventUser

#     <b>🔅 Событие: Пользователь удален из панели!</b>

#     { hdr-user }
#     { frg-user-info }

#     { hdr-subscription }
#     { frg-subscription-details }

ntf-event-user-first-connected =
    #EventUser

    <b>🔅 Событие: Первое подключение пользователя!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }

ntf-event-user-expiring =
    <b>⚠️ Внимание! Ваша подписка истекает через { unit-day }.</b>

ntf-event-user-expired =
    <b>⛔ Внимание! Доступ приостановлен — VPN не работает.</b>

    Ваша подписка истекла, продлите ее, чтобы продолжить пользоваться VPN!

ntf-event-user-expired_ago =
    <b>⛔ Внимание! Доступ приостановлен — VPN не работает.</b>

    Ваша подписка истекла {unit-day} назад, продлите ее, чтобы продолжить пользоваться VPN!

ntf-event-user-limited =
    <b>⛔ Внимание! Доступ приостановлен — VPN не работает.</b>

    Вы исчерпали лимит трафика, продлите подписку, чтобы продолжить пользоваться VPN!

ntf-event-user-hwid-added =
    #EventUserHwid

    <b>🔅 Событие: Добавлено новое устройство у пользователя!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

ntf-event-user-hwid-deleted =
    #EventUserHwid

    <b>🔅 Событие: Удалено устройство у пользователя!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

ntf-event-user-referral-attached =
    <b>🎉 Вы пригласили друга!</b>
    
    <blockquote>
    Пользователь <b>{ $name }</b> присоединился по вашей пригласительной ссылке! Чтобы получить награду, убедитесь, что он совершит покупку подписки.
    </blockquote>

ntf-event-user-referral-qualified =
    <b>✅ Реферал квалифицирован!</b>
    
    <blockquote>
    Пользователь <b>{ $name }</b> выполнил условия квалификации и теперь учитывается в реферальной программе.
    </blockquote>

ntf-event-user-referral-reward =
    <b>💰 Вам начислена награда!</b>
    
    <blockquote>
    Пользователь <b>{ $name }</b> совершил платеж. Вы получили <b>{ $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] балл
        [few] балла
        *[more] баллов 
        }
    [EXTRA_DAYS] доп. { $value -> 
        [one] день
        [few] дня
        *[more] дней
        }
    *[OTHER] { $reward_type }
    }</b> к вашей подписке!
    </blockquote>

ntf-event-user-referral-reward-error =
    <b>❌ Не получилось выдать награду!</b>
    
    <blockquote>
    Пользователь <b>{ $name }</b> совершил платеж, но мы не смогли начислить вам вознаграждение из-за того что <b>у вас нет купленной подписки</b>, к которой можно было бы добавить {$value} { $value ->
            [one] доп. день
            [few] доп. дня
            *[more] доп. дней
        }.
    
    <i>Купите подписку, чтобы получать бонусы за приглашенных друзей!</i>
    </blockquote>


# Notifications
ntf-command-paysupport = 💸 <b>Чтобы запросить возврат, обратитесь в нашу службу поддержки.</b>
ntf-command-help = 🆘 <b>Нажмите кнопку ниже, чтобы связаться с поддержкой. Мы поможем решить вашу проблему.</b>
ntf-channel-join-required = ❇️ Подпишитесь на наш канал и получайте <b>бесплатные дни, акции и новости</b>! После подписки нажмите кнопку «Подтвердить».
ntf-channel-join-required-left = ⚠️ Вы отписались от нашего канала! Подпишитесь, чтобы иметь возможность пользоваться ботом.
ntf-rules-accept-required = ⚠️ <b>Перед использованием сервиса, пожалуйста, ознакомьтесь и примите <a href="{ $url }">Условия использования</a> сервиса.</b>

ntf-double-click-confirm = <i>⚠️ Нажмите еще раз, чтобы подтвердить действие.</i>
ntf-channel-join-error = <i>⚠️ Мы не видим вашу подписку на канал. Проверьте, что вы подписались, и попробуйте еще раз.</i>
ntf-throttling-many-requests = <i>⚠️ Вы отправляете слишком много запросов, пожалуйста, подождите немного.</i>
ntf-squads-empty = <i>⚠️ Сквады не найдены. Проверьте их наличие в панели.</i>
ntf-invite-withdraw-points-error = ❌ У вас недостаточно баллов для выполнения обмена.
ntf-exchange-points-no-points = <i>❌ У вас нет баллов для обмена.</i>
ntf-exchange-points-success = <i>✅ Успешно! Вы обменяли <b>{ $points }</b> баллов на <b>{ $days }</b> дней подписки.</i>
ntf-exchange-points-disabled = <i>❌ Обмен баллов временно отключен.</i>
ntf-exchange-points-min-not-reached = <i>❌ Минимальное количество баллов для обмена: <b>{ $min_points }</b>.</i>
ntf-exchange-points-max-exceeded = <i>❌ Максимальное количество баллов за один обмен: <b>{ $max_points }</b>.</i>
ntf-points-exchange-invalid-value = <i>❌ Некорректное значение. Введите положительное число.</i>
ntf-points-exchange-updated = <i>✅ Настройки обмена баллов успешно обновлены.</i>

ntf-connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] Вы израсходовали весь доступный объем трафика. Теперь ваш доступ ограничен до покупки новой подписки.
    [EXPIRED] Срок действия вашей подписки истек. Чтобы продолжить пользоваться сервисом, продлите подписку или оформите новую.
    *[OTHER] Произошла ошибка при проверке статуса или ваша подписка была отключена. Попробуйте обновить данные или обратиться в поддержку.
    }

ntf-connect-device-url =
    <b>🔗 Ссылка для подключения</b>

    <blockquote>
    <code>{ $url }</code>
    </blockquote>

    <i>Скопируйте ссылку и вставьте в приложение для подключения.</i>

ntf-subscription-not-found = <i>❌ Подписка не найдена.</i>

ntf-user-not-found = <i>❌ Пользователь не найден.</i>
ntf-user-transactions-empty = <i>❌ Список транзакций пуст.</i>
ntf-user-subscription-empty = <i>❌ Подписки пользователя не найдены.</i>
ntf-user-plans-empty = <i>❌ Нет доступных планов для выдачи.</i>
ntf-user-devices-empty = <i>❌ Список устройств пуст.</i>
ntf-user-invalid-number = <i>❌ Некорректное число.</i>
ntf-user-allowed-plans-empty = <i>❌ Нет доступных планов для предоставления доступа.</i>
ntf-user-message-success = <i>✅ Сообщение успешно отправлено.</i>
ntf-user-message-not-sent = <i>❌ Не удалось отправить сообщение.</i>
ntf-user-sync-failed = <i>❌ Не удалось синхронизировать пользователя.</i>
ntf-user-sync-success = <i>✅ Синхронизация пользователя выполнена.</i>

ntf-user-invalid-expire-time = <i>❌ Невозможно { $operation ->
    [ADD] продлить подписку на указанное количество дней
    *[SUB] уменьшить срок подписки на указанное количество дней
    }.</i>

ntf-user-invalid-points = <i>❌ Невозможно { $operation ->
    [ADD] добавить указанное количество баллов
    *[SUB] отнять указанное количество баллов
    }.</i>

ntf-referral-invalid-reward = <i>❌ Некорректное значение.</i>

ntf-access-denied = <i>🚧 Бот в режиме обслуживания, попробуйте позже.</i>
ntf-access-denied-registration = <i>❌ Регистрация новых пользователей отключена.</i>
ntf-access-denied-only-invited = <i>❌ Регистрация новых пользователей доступна только через приглашение другим пользователем.</i>
ntf-access-denied-purchasing = <i>🚧 Бот в режиме обслуживания, Вам придет уведомление когда бот снова будет доступен.</i>
ntf-access-allowed = <i>❇️ Весь функционал бота снова доступен, спасибо за ожидание.</i>
ntf-access-id-saved = <i>✅ ID канала/группы успешно обновлен.</i>
ntf-access-link-saved = <i>✅ Ссылка на канал/группу успешно обновлена.</i>
ntf-access-channel-invalid = <i>❌ Некорректная ссылка или ID канала/группы.</i>

ntf-plan-invalid-name = <i>❌ Некорректное имя.</i>
ntf-plan-invalid-description = <i>❌ Некорректное описание.</i>
ntf-plan-invalid-tag = <i>❌ Некорректный тег.</i>
ntf-plan-invalid-number = <i>❌ Некорректное число.</i>
ntf-plan-trial-once-duration = <i>❌ Пробный план может иметь только одну длительность.</i>
ntf-plan-trial-already-exists = <i>❌ Пробный план уже существует.</i>
ntf-plan-duration-already-exists = <i>❌ Такая длительность уже существует.</i>
ntf-plan-duration-last = <i>❌ Нельзя удалить последнюю длительность.</i>
ntf-plan-save-error = <i>❌ Ошибка сохранения плана.</i>
ntf-plan-name-already-exists = <i>❌ План с таким именем уже существует.</i>
ntf-plan-invalid-user-id = <i>❌ Некорректный ID пользователя.</i>
ntf-plan-no-user-found = <i>❌ Пользователь не найден.</i>
ntf-plan-user-already-allowed = <i>❌ Пользователь уже добавлен в список разрешенных.</i>
ntf-plan-confirm-delete = <i>⚠️ Нажмите еще раз, чтобы удалить.</i>
ntf-plan-updated-success = <i>✅ План успешно обновлен.</i>
ntf-plan-created-success = <i>✅ План успешно создан.</i>
ntf-plan-deleted-success = <i>✅ План успешно удален.</i>
ntf-plan-internal-squads-empty = <i>❌ Выберите хотя бы один внутренний сквад.</i>

ntf-gateway-not-configured = <i>❌ Платежный шлюз не настроен.</i>
ntf-gateway-not-configurable = <i>❌ Платежный шлюз не имеет настроек.</i>
ntf-gateway-field-wrong-value = <i>❌ Некорректное значение.</i>
ntf-gateway-test-payment-created = <i>✅ <a href="{ $url }">Тестовый платеж</a> успешно создан.</i>
ntf-gateway-test-payment-error = <i>❌ Произошла ошибка при создании тестового платежа.</i>
ntf-gateway-test-payment-confirmed = <i>✅ Тестовый платеж успешно обработан.</i>

ntf-subscription-plans-not-available = <i>❌ Нет доступных планов.</i>
ntf-subscription-gateways-not-available = <i>❌ Нет доступных платежных систем.</i>
ntf-subscription-renew-plan-unavailable = <i>❌ Ваш план устарел и не доступен для продления.</i>
ntf-subscription-payment-creation-failed = <i>❌ Произошла ошибка при создании платежа, попробуйте позже.</i>
ntf-subscription-limit-exceeded = <i>❌ Превышен лимит подписок. У вас уже { $current } подписок из { $max } возможных.</i>
ntf-subscription-deleted = <i>✅ Подписка успешно удалена.</i>
ntf-subscription-select-at-least-one = <i>❌ Выберите хотя бы одну подписку для продления.</i>

ntf-broadcast-list-empty = <i>❌ Список рассылок пуст.</i>
ntf-broadcast-audience-not-available = <i>❌ Нет доступных пользователей для выбранной аудитории.</i>
ntf-broadcast-audience-not-active = <i>❌ Нет пользователей у которых есть АКТИВНАЯ подписка с данным планом.</i>
ntf-broadcast-plans-not-available = <i>❌ Нет доступных планов.</i>
ntf-broadcast-empty-content = <i>❌ Контент пустой.</i>
ntf-broadcast-wrong-content = <i>❌ Некорректный контент.</i>
ntf-broadcast-content-saved = <i>✅ Контент сообщения успешно сохранен.</i>
ntf-broadcast-promocode-code-required = <i>❌ Сначала укажите промокод.</i>
ntf-broadcast-promocode-saved = <i>✅ Промокод <b>{ $code }</b> сохранен для этой рассылки.</i>
ntf-broadcast-promocode-cleared = <i>✅ Промокод удален из этой рассылки.</i>
ntf-broadcast-promocode-button-enabled = <i>✅ Кнопка промокода включена для этой рассылки.</i>
ntf-broadcast-promocode-button-disabled = <i>✅ Кнопка промокода выключена для этой рассылки.</i>
ntf-broadcast-promocode-webapp-missing = <i>❌ Для кнопки промокода нужен WEB_APP_URL или URL в BOT_MINI_APP.</i>
ntf-broadcast-preview = { $content }
ntf-broadcast-not-cancelable = <i>❌ Рассылка не может быть отменена.</i>
ntf-broadcast-canceled = <i>✅ Рассылка успешно отменена.</i>
ntf-broadcast-deleting = <i>⚠️ Идет удаление всех отправленных сообщений.</i>
ntf-broadcast-already-deleted = <i>❌ Рассылка находится в процессе удаления или уже удалена.</i>

ntf-broadcast-deleted-success =
    ✅ Рассылка <code>{ $task_id }</code> успешно удалена.

    <blockquote>
    • <b>Всего сообщений</b>: { $total_count }
    • <b>Успешно удалено</b>: { $deleted_count }
    • <b>Не удалось удалить</b>: { $failed_count }
    </blockquote>

ntf-trial-unavailable = <i>❌ Пробная подписка временно недоступна.</i>

# Multi Subscription
ntf-multi-subscription-invalid-value = <i>❌ Некорректное значение. Введите положительное число или -1 для безлимита.</i>
ntf-multi-subscription-disabled = <i>❌ Мультиподписка отключена. Сначала включите её в настройках RemnaShop.</i>
ntf-multi-subscription-updated = <i>✅ Настройки мультиподписки обновлены.</i>

# Promocodes
ntf-promocode-not-found = <i>❌ Промокод не найден.</i>
ntf-promocode-inactive = <i>❌ Промокод неактивен.</i>
ntf-promocode-expired = <i>❌ Срок действия промокода истек.</i>
ntf-promocode-depleted = <i>❌ Промокод исчерпал лимит активаций.</i>
ntf-promocode-already-activated = <i>❌ Вы уже активировали этот промокод.</i>
ntf-promocode-not-available = <i>❌ Промокод недоступен для вас.</i>
ntf-promocode-reward-failed = <i>❌ Не удалось применить награду промокода.</i>
ntf-promocode-activation-error = <i>❌ Произошла ошибка при активации промокода. Попробуйте позже.</i>
ntf-promocode-error = <i>❌ Произошла ошибка при активации промокода.</i>
ntf-promocode-no-subscription = <i>❌ Для активации этого промокода необходима активная подписка.</i>
ntf-promocode-no-subscription-for-duration = <i>❌ У вас нет активных подписок, к которым можно добавить дни. Сначала приобретите подписку.</i>

ntf-promocode-activated = <i>✅ Промокод <b>{ $code }</b> успешно активирован!</i>
ntf-promocode-activated-duration = <i>✅ Промокод <b>{ $code }</b> активирован! Вам добавлено { $reward } к подписке.</i>
ntf-promocode-activated-traffic = <i>✅ Промокод <b>{ $code }</b> активирован! Вам добавлено { $reward } трафика.</i>
ntf-promocode-activated-devices = <i>✅ Промокод <b>{ $code }</b> активирован! Вам добавлено { $reward } устройств.</i>
ntf-promocode-activated-subscription = <i>✅ Промокод <b>{ $code }</b> активирован! Вам выдана подписка.</i>
ntf-promocode-activated-subscription-extended = <i>✅ Промокод <b>{ $code }</b> активирован! К вашей подписке добавлено { $days } { $days ->
    [1] день
    [2] дня
    [3] дня
    [4] дня
    *[other] дней
    }.</i>
ntf-promocode-activated-personal-discount = <i>✅ Промокод <b>{ $code }</b> активирован! Вам установлена персональная скидка { $reward }.</i>
ntf-promocode-activated-purchase-discount = <i>✅ Промокод <b>{ $code }</b> активирован! Вам установлена скидка на следующую покупку { $reward }.</i>

ntf-promocode-code-required = <i>❌ Укажите код промокода.</i>
ntf-promocode-plan-required = <i>❌ Выберите план для промокода типа "Подписка".</i>
ntf-promocode-reward-required = <i>❌ Укажите награду промокода.</i>
ntf-promocode-allowed-users-required = <i>❌ Добавьте хотя бы одного пользователя для режима ALLOWED.</i>
ntf-promocode-code-exists = <i>❌ Промокод с таким кодом уже существует.</i>
ntf-promocode-created = <i>✅ Промокод успешно создан.</i>
ntf-promocode-updated = <i>✅ Промокод успешно обновлен.</i>
ntf-promocode-deleted = <i>✅ Промокод успешно удален.</i>
ntf-invalid-value = <i>❌ Некорректное значение.</i>

ntf-event-promocode-activated =
    #EventPromocodeActivated

    <b>🔅 Событие: Активация промокода!</b>

    { hdr-user }
    { frg-user-info }

    <b>🎟 Промокод:</b>
    <blockquote>
    • <b>Код</b>: { $code }
    • <b>Тип награды</b>: { $reward_type }
    • <b>Награда</b>: { $reward }
    </blockquote>

ntf-importer-not-file = <i>⚠️ Отправьте базу данных в виде файла.</i>
ntf-importer-db-invalid = <i>❌ Этот файл не может быть импортирован.</i>
ntf-importer-db-failed = <i>❌ Ошибка при импорте базы данных.</i>
ntf-importer-exported-users-empty =  <i>❌ Список пользователей в базе данных пуст.</i>
ntf-importer-internal-squads-empty = <i>❌ Выберите хотя бы один внутренний сквад.</i>
ntf-importer-import-started = <i>✅ Импорт пользователей запущен, ожидайте...</i>
ntf-importer-sync-started = <i>✅ Синхронизация пользователей запущена, ожидайте...</i>
ntf-importer-users-not-found = <i>❌ Не удалось найти пользователей для синхронизации.</i>
ntf-importer-not-support = <i>⚠️ Импорт всех данных из 3xui-shop временно недоступен. Вы можете воспользоваться импортом из панели 3X-UI!</i>


# Partner Program
ntf-partner-created = <i>✅ Партнерка успешно выдана пользователю.</i>
ntf-partner-activated = <i>✅ Партнерка активирована.</i>
ntf-partner-deactivated = <i>✅ Партнерка деактивирована.</i>
ntf-partner-deleted = <i>✅ Партнерка удалена.</i>
ntf-partner-already-exists = <i>❌ У пользователя уже есть партнерка.</i>
ntf-partner-not-found = <i>❌ Партнерка не найдена.</i>
ntf-partner-disabled = <i>❌ Партнерская программа отключена.</i>

ntf-partner-balance-insufficient = <i>❌ Недостаточный баланс для снятия указанной суммы.</i>
ntf-partner-balance-updated = <i>✅ Баланс партнера успешно изменен.</i>
ntf-partner-balance-invalid-amount = <i>❌ Некорректная сумма. Введите число (положительное для добавления, отрицательное для снятия).</i>

ntf-partner-invalid-percent = <i>❌ Некорректный процент. Введите число от 0 до 100.</i>
ntf-partner-invalid-amount = <i>❌ Некорректная сумма. Введите положительное число.</i>
ntf-partner-invalid-level = <i>❌ Некорректный уровень. Допустимые значения: 1, 2, 3.</i>
ntf-partner-percent-updated = <i>✅ Процент для уровня { $level } обновлен на { $percent }%.</i>
ntf-partner-tax-updated = <i>✅ Налоговая ставка обновлена на { $percent }%.</i>
ntf-partner-gateway-fee-updated = <i>✅ Комиссия платежной системы обновлена на { $percent }%.</i>
ntf-partner-min-withdrawal-updated = <i>✅ Минимальная сумма вывода обновлена на { $amount }.</i>
ntf-partner-settings-updated = <i>✅ Настройки партнерской программы обновлены.</i>
ntf-partner-individual-settings-updated = <i>✅ Индивидуальные настройки партнера обновлены.</i>
ntf-partner-invalid-percent-format = <i>❌ Некорректный формат. Введите в формате: <code>уровень процент</code> (например: 1 15)</i>
ntf-partner-invalid-amount-format = <i>❌ Некорректная сумма. Введите положительное число.</i>

ntf-partner-withdraw-min-not-reached = <i>❌ Минимальная сумма для вывода: { $min_withdrawal }.</i>
ntf-partner-withdraw-insufficient-balance = <i>❌ Недостаточно средств на балансе.</i>
ntf-partner-withdraw-request-created = <i>✅ Заявка на вывод создана и отправлена на рассмотрение.</i>
ntf-partner-balance-currency-updated = <i>✅ Валюта партнерского баланса обновлена: { $currency }.</i>
ntf-partner-withdraw-approved = <i>✅ Заявка на вывод одобрена.</i>
ntf-partner-withdraw-rejected = <i>❌ Заявка на вывод отклонена.</i>
ntf-partner-withdraw-already-processed = <i>❌ Заявка уже обработана.</i>

ntf-partner-withdrawals-empty = <i>📭 Нет заявок на вывод.</i>

# Admin notifications for withdrawal processing
ntf-partner-withdrawal-approved = <i>✅ Запрос на вывод успешно выполнен.</i>
ntf-partner-withdrawal-pending-set = <i>💭 Запрос отмечен как "На рассмотрении".</i>
ntf-partner-withdrawal-rejected = <i>🚫 Запрос на вывод отклонен.</i>
ntf-partner-withdrawal-error = <i>❌ Ошибка при обработке запроса на вывод.</i>

# User (partner) notifications about withdrawal status
ntf-partner-withdrawal-completed =
    <b>✅ Ваш запрос на вывод выполнен!</b>
    
    <blockquote>
    Сумма <b>{ $amount }</b> руб. была успешно выведена.
    </blockquote>

ntf-partner-withdrawal-under-review =
    <b>💭 Ваш запрос на вывод на рассмотрении</b>
    
    <blockquote>
    Заявка на вывод <b>{ $amount }</b> руб. принята на рассмотрение.
    Ожидайте решения администратора.
    </blockquote>

ntf-partner-withdrawal-rejected-user =
    <b>🚫 Ваш запрос на вывод отклонен</b>
    
    <blockquote>
    Заявка на вывод <b>{ $amount }</b> руб. была отклонена.
    Причина: { $reason }
    Средства возвращены на ваш партнерский баланс.
    </blockquote>

ntf-event-partner-earning =
    <b>💰 Начисление партнерской программы!</b>
    
    <blockquote>
    Реферал <b>{ $referral_name }</b> ({ $level ->
        [1] 1️⃣ уровень
        [2] 2️⃣ уровень
        [3] 3️⃣ уровень
        *[OTHER] { $level } уровень
    }) совершил оплату.
    Вам начислено <b>+{ $amount }</b>!
    </blockquote>
    
    <b>Ваш баланс:</b> { $new_balance }

ntf-event-partner-referral-registered =
    <b>🤝 Новый партнерский реферал!</b>
    
    <blockquote>
    По вашей партнерской ссылке зарегистрировался пользователь <b>{ $name }</b>.
    </blockquote>

ntf-event-partner-withdrawal-approved =
    <b>✅ Заявка на вывод одобрена!</b>
    
    <blockquote>
    Ваша заявка на вывод <b>{ $amount }</b> была одобрена администратором.
    </blockquote>

ntf-event-partner-withdrawal-rejected =
    <b>❌ Заявка на вывод отклонена</b>
    
    <blockquote>
    Ваша заявка на вывод <b>{ $amount }</b> была отклонена.
    Средства возвращены на партнерский баланс.
    </blockquote>

ntf-event-partner-withdrawal-request =
    #EventPartnerWithdrawal
    
    <b>🔅 Событие: Новая заявка на вывод!</b>
    
    { hdr-user }
    { frg-user-info }
    
    <b>💸 Заявка:</b>
    <blockquote>
    • <b>Сумма</b>: { $amount }
    • <b>Баланс партнера</b>: { $partner_balance }
    </blockquote>

# Backup System
ntf-backup-creating = <i>🔄 Создание бэкапа базы данных...</i>
ntf-backup-created-success = <i>✅ Бэкап создан успешно!</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-created-failed = <i>❌ Ошибка создания бэкапа</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-restoring = <i>📥 Восстановление из бэкапа...</i>

    <blockquote>
    • <b>Файл</b>: <code>{ $filename }</code>
    • <b>Очистка данных</b>: { $clear_existing ->
        [true] Да
        *[false] Нет
    }
    </blockquote>

ntf-backup-restored-success = <i>✅ Восстановление завершено!</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-restored-failed = <i>❌ Ошибка восстановления</i>

    <blockquote>
    { $message }
    </blockquote>
# Importer plan assignment notifications
ntf-importer-sync-warning-no-active-plans = <i>⚠️ Перед синхронизацией: сначала создайте и активируйте план, иначе массовое назначение для этого запуска будет недоступно. Нажмите еще раз для запуска sync.</i>
ntf-importer-sync-warning-has-active-plans = <i>ℹ️ После синхронизации вы сможете назначить выбранный план всем пользователям из этого запуска. Индивидуальная корректировка доступна в профиле пользователя. Нажмите еще раз для запуска sync.</i>
ntf-importer-assign-plan-all-started = <i>⏳ Массовое назначение плана запущено, ожидайте...</i>
ntf-importer-assign-plan-all-done = <i>✅ Массовое назначение завершено.</i>

    <blockquote>
    Обновлено подписок: { $updated }
    Пропущено (нет текущей подписки): { $skipped_no_subscription }
    Пропущено (удаленная подписка): { $skipped_deleted }
    Пропущено (уже назначены вручную): { $skipped_already_assigned }
    Ошибки: { $errors }
    </blockquote>

ntf-importer-assign-plan-all-no-users = <i>❌ Нет пользователей из последней синхронизации для массового назначения.</i>
ntf-importer-assign-plan-all-no-plan = <i>❌ Сначала выберите план для массового назначения.</i>

# User plan assignment notifications
ntf-user-assign-plans-empty = <i>❌ Нет активных планов для назначения.</i>
ntf-user-plan-assigned = <i>✅ План <b>{ $plan_name }</b> назначен текущей подписке пользователя.</i>

ntf-event-web-user-registered =
    #EventWebUserRegistered

    <b>🆕 Событие: Регистрация пользователя через Web!</b>

    { hdr-user }
    { frg-user-info }

    <b>🌐 Web:</b>
    <blockquote>
    • <b>Логин</b>: <code>{ $web_username }</code>
    • <b>Источник</b>: { $auth_source }
    </blockquote>

ntf-event-web-account-linked =
    #EventWebAccountLinked

    <b>🔗 Событие: Web аккаунт синхронизирован с Telegram!</b>

    { hdr-user }
    { frg-user-info }

    <b>🌐 Связка:</b>
    <blockquote>
    • <b>Логин</b>: <code>{ $web_username }</code>
    • <b>Старый ID профиля</b>: <code>{ $old_user_id }</code>
    • <b>Новый Telegram ID</b>: <code>{ $linked_telegram_id }</code>
    </blockquote>

ntf-user-web-password-reset-issued =
    🔐 Временный web-пароль выдан.

    <blockquote>
    • Логин: <code>{ $username }</code>
    • Пароль: <code>{ $temp_password }</code>
    • Действует до: <b>{ $expires_at }</b>
    </blockquote>

    Передайте пароль пользователю вручную. При первом входе потребуется смена пароля.

ntf-user-web-password-reset-failed = ❌ Не удалось сбросить web-пароль: { $error }
ntf-plan-delete-blocked = <i>❌ План нельзя удалить, пока он используется в подписках или переходах. Переведите его в архив.</i>
ntf-plan-validation-error = <i>❌ Ошибка валидации плана: { $error }</i>
ntf-referral-invite-link-unavailable = <i>⚠️ Активная invite-ссылка сейчас недоступна. Проверьте срок действия и свободные слоты.</i>
ntf-referral-invite-regenerated = <i>✅ Новая invite-ссылка успешно создана.</i>
ntf-referral-invite-regenerate-blocked = <i>🚫 Нельзя выпустить новую ссылку: свободные слоты приглашений закончились.</i>
ntf-access-denied-only-invited-soft = <i>🔒 Этот раздел доступен только приглашённым пользователям. Откройте бота по валидной invite-ссылке.</i>
