"""API request contracts and lightweight request mappers."""

from src.api.contracts.user_account import SetSecurityEmailRequest
from src.api.contracts.user_portal import (
    PartnerWithdrawalRequest,
    ReferralExchangeExecuteRequest,
)
from src.api.contracts.user_subscription import (
    GenerateDeviceRequest,
    PromocodeActivateRequest,
    PurchaseRequest,
    SubscriptionAssignmentRequest,
    TrialRequest,
    build_subscription_assignment_update,
    build_subscription_purchase_request,
)
from src.api.contracts.web_auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordTelegramRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordByCodeRequest,
    ResetPasswordByLinkRequest,
    ResetPasswordByTelegramCodeRequest,
    TelegramAuthRequest,
    TelegramLinkConfirmPayload,
    TelegramLinkRequestPayload,
    VerifyEmailConfirmRequest,
    WebAccountBootstrapRequest,
)

__all__ = [
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "ForgotPasswordTelegramRequest",
    "GenerateDeviceRequest",
    "LoginRequest",
    "PartnerWithdrawalRequest",
    "PromocodeActivateRequest",
    "PurchaseRequest",
    "RegisterRequest",
    "ReferralExchangeExecuteRequest",
    "ResetPasswordByCodeRequest",
    "ResetPasswordByLinkRequest",
    "ResetPasswordByTelegramCodeRequest",
    "SetSecurityEmailRequest",
    "SubscriptionAssignmentRequest",
    "TelegramAuthRequest",
    "TelegramLinkConfirmPayload",
    "TelegramLinkRequestPayload",
    "TrialRequest",
    "VerifyEmailConfirmRequest",
    "WebAccountBootstrapRequest",
    "build_subscription_assignment_update",
    "build_subscription_purchase_request",
]
