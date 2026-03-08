from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Optional

from loguru import logger

from src.core.config import AppConfig


class EmailSenderService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        email_cfg = self.config.email
        if (
            not email_cfg.enabled
            or not email_cfg.host
            or not email_cfg.from_address
            or not to_email
        ):
            logger.warning(
                "Email sending skipped: SMTP is disabled or required settings are missing"
            )
            return False

        message = EmailMessage()
        sender_name = email_cfg.from_name.strip() if email_cfg.from_name else ""
        from_address = (
            f"{sender_name} <{email_cfg.from_address}>" if sender_name else email_cfg.from_address
        )
        message["From"] = from_address
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            await asyncio.to_thread(self._send_sync, message)
            return True
        except Exception as exc:
            logger.error(f"Failed to send email to '{to_email}': {exc}")
            return False

    def _send_sync(self, message: EmailMessage) -> None:
        email_cfg = self.config.email
        username = email_cfg.username.get_secret_value() if email_cfg.username else None
        password = email_cfg.password.get_secret_value() if email_cfg.password else None

        if email_cfg.use_ssl:
            with smtplib.SMTP_SSL(host=email_cfg.host, port=email_cfg.port, timeout=15) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(host=email_cfg.host, port=email_cfg.port, timeout=15) as smtp:
            smtp.ehlo()
            if email_cfg.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
