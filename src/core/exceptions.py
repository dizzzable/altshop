"""Custom exceptions for the remnashop application."""


class MenuRenderingError(Exception):
    """Raised when main menu cannot be rendered."""


class SubscriptionNotFoundError(Exception):
    """Raised when subscription is not found."""


class UserNotFoundError(Exception):
    """Raised when user is not found."""


class PlanNotFoundError(Exception):
    """Raised when plan is not found."""


class PaymentError(Exception):
    """Raised when payment processing fails."""


class RemnawaveError(Exception):
    """Raised when Remnawave API call fails."""