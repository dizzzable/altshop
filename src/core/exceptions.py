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


PurchaseErrorDetail = str | dict[str, str]


class SubscriptionPurchaseError(Exception):
    """Raised when subscription purchase validation or execution fails."""

    def __init__(self, *, status_code: int, detail: PurchaseErrorDetail) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))
