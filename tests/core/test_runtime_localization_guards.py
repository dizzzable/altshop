from pathlib import Path


def test_targeted_bot_runtime_strings_use_i18n_keys() -> None:
    backup_getters = Path("src/bot/routers/dashboard/backup/getters.py").read_text(
        encoding="utf-8"
    )
    backup_handlers = Path("src/bot/routers/dashboard/backup/handlers.py").read_text(
        encoding="utf-8"
    )
    backup_dialog = Path("src/bot/routers/dashboard/backup/dialog.py").read_text(
        encoding="utf-8"
    )
    banner_handlers = Path(
        "src/bot/routers/dashboard/remnashop/banners/handlers.py"
    ).read_text(encoding="utf-8")
    menu_getters = Path("src/bot/routers/menu/getters.py").read_text(encoding="utf-8")
    menu_handlers = Path("src/bot/routers/menu/handlers.py").read_text(encoding="utf-8")
    multisubscription_getters = Path(
        "src/bot/routers/dashboard/remnashop/multisubscription/getters.py"
    ).read_text(encoding="utf-8")
    partner_getters = Path(
        "src/bot/routers/dashboard/remnashop/partner/getters.py"
    ).read_text(encoding="utf-8")
    branding_getters = Path(
        "src/bot/routers/dashboard/remnashop/branding/getters.py"
    ).read_text(encoding="utf-8")
    branding_dialog = Path(
        "src/bot/routers/dashboard/remnashop/branding/dialog.py"
    ).read_text(encoding="utf-8")
    branding_handlers = Path(
        "src/bot/routers/dashboard/remnashop/branding/handlers.py"
    ).read_text(encoding="utf-8")
    bot_menu_dialog = Path(
        "src/bot/routers/dashboard/remnashop/bot_menu/dialog.py"
    ).read_text(encoding="utf-8")
    bot_menu_getters = Path(
        "src/bot/routers/dashboard/remnashop/bot_menu/getters.py"
    ).read_text(encoding="utf-8")
    bot_menu_handlers = Path(
        "src/bot/routers/dashboard/remnashop/bot_menu/handlers.py"
    ).read_text(encoding="utf-8")

    assert "msg-backup-scope-db-label" in backup_getters
    assert "msg-backup-source-local" in backup_getters
    assert "msg-backup-content-source" in backup_getters
    assert "msg-backup-scope-title" in backup_dialog
    assert "msg-backup-import" in backup_dialog
    assert "ntf-backup-creation-started" in backup_handlers
    assert "ntf-backup-imported-success" in backup_handlers
    assert "ntf-banner-upload-success" in banner_handlers
    assert "msg-common-plan-fallback" in menu_getters
    assert "msg-common-empty-value" in menu_getters
    assert "msg-menu-invite-referral-row" in menu_getters
    assert "msg-common-plan-fallback" in menu_handlers
    assert "msg-common-unlimited" in multisubscription_getters
    assert "msg-common-empty-value" in partner_getters
    assert "msg-branding-field-project-name" in branding_getters
    assert "msg-branding-edit-locale-en" in branding_getters
    assert "project_name_label" in branding_dialog
    assert "edit_locale_en_label" in branding_dialog
    assert "ntf-branding-field-not-selected" in branding_handlers
    assert "ntf-branding-save-failed" in branding_handlers
    assert "msg-bot-menu-main" in bot_menu_dialog
    assert "msg-bot-menu-source-settings" in bot_menu_getters
    assert "msg-bot-menu-new-button-label" in bot_menu_handlers
    assert "ntf-bot-menu-button-created" in bot_menu_handlers
    assert "ntf-bot-menu-mode-missing-url" in bot_menu_handlers

    forbidden_literals = {
        "Database only": [backup_getters, backup_dialog],
        "Assets only": [backup_getters, backup_dialog],
        "Full backup": [backup_getters, backup_dialog],
        "Choose backup scope": [backup_dialog],
        "No backups found": [backup_dialog],
        "Backup creation started": [backup_handlers],
        "Restore started": [backup_handlers],
        "Backup deleted": [backup_handlers],
        "Import backup": [backup_dialog, backup_handlers],
        "Delete local copy": [backup_dialog, backup_getters],
        "Local + Telegram": [backup_getters],
        "Select a banner first.": [banner_handlers],
        "Project Name": [branding_getters, branding_dialog],
        "Web Title": [branding_getters, branding_dialog],
        "Bot Menu Button": [branding_getters, branding_dialog],
        "TG Template": [branding_getters, branding_dialog],
        "Edit EN (Base)": [branding_getters, branding_dialog],
        "Edit RU (Override)": [branding_getters, branding_dialog],
        "No branding field selected.": [branding_handlers],
        "Failed to save value:": [branding_handlers],
        "Mini App URL": [bot_menu_dialog, bot_menu_getters, bot_menu_handlers],
        "Custom Button": [bot_menu_dialog, bot_menu_getters, bot_menu_handlers],
        "Mini App-first": [bot_menu_dialog, bot_menu_getters, bot_menu_handlers],
        "Custom button not found": [bot_menu_handlers],
        "New Button": [bot_menu_handlers],
        "РџРѕРґРїРёСЃРєР°": [menu_handlers, multisubscription_getters],
        "в€ћ (Р±РµР·Р»РёРјРёС‚)": [multisubscription_getters],
        "РќРµ СѓРєР°Р·Р°РЅС‹": [partner_getters],
    }

    hits: list[str] = []
    for literal, sources in forbidden_literals.items():
        for source in sources:
            if literal in source:
                hits.append(literal)
                break

    assert hits == []


def test_targeted_web_runtime_strings_use_locale_map() -> None:
    login_page = Path("web-app/src/pages/auth/LoginPage.tsx").read_text(encoding="utf-8")
    register_page = Path("web-app/src/pages/auth/RegisterPage.tsx").read_text(encoding="utf-8")
    forgot_page = Path("web-app/src/pages/auth/ForgotPasswordPage.tsx").read_text(
        encoding="utf-8"
    )
    reset_page = Path("web-app/src/pages/auth/ResetPasswordPage.tsx").read_text(
        encoding="utf-8"
    )
    devices_page = Path("web-app/src/pages/dashboard/DevicesPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "auth.login.usernamePlaceholder" in login_page
    assert "auth.login.passwordPlaceholder" in login_page
    assert "auth.register.telegramIdPlaceholder" in register_page
    assert "auth.register.usernamePlaceholder" in register_page
    assert "auth.register.passwordPlaceholder" in register_page
    assert "auth.forgot.emailPlaceholder" in forgot_page
    assert "auth.reset.emailPlaceholder" in reset_page
    assert "auth.reset.newPasswordPlaceholder" in reset_page
    assert "devices.toast.loadFailed" in devices_page

    forbidden_literals = [
        "Failed to load devices",
        'placeholder="username"',
        'placeholder="you@example.com"',
        'placeholder="123456789"',
        'placeholder="вЂўвЂўвЂўвЂўвЂўвЂўвЂўвЂў"',
    ]
    sources = [login_page, register_page, forgot_page, reset_page, devices_page]

    hits: list[str] = []
    for literal in forbidden_literals:
        if any(literal in source for source in sources):
            hits.append(literal)

    assert hits == []
