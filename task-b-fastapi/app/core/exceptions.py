"""Domain-level exceptions maintaining clean separation from HTTP transport concerns."""


class DomainException(Exception):
    """Base exception for all domain and business logic errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class EntityNotFoundError(DomainException):
    """Raised when a requested resource does not exist within the tenant scope."""
    def __init__(self, entity_name: str, entity_id: str):
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name} with ID '{entity_id}' not found.")


class ForbiddenActionError(DomainException):
    """Raised when a user lacks sufficient role permissions to perform an operation."""
    pass


class TenantViolationError(DomainException):
    """Raised when an operation attempts to breach tenant data isolation."""
    pass


class InvalidStateTransitionError(DomainException):
    """Raised when an illegal task status transition is attempted."""
    def __init__(self, from_status: str, to_status: str, reason: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        detail = f" Cannot transition task from '{from_status}' to '{to_status}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(detail)


class BusinessRuleViolationError(DomainException):
    """Raised when business validation fails (e.g. assigning task to user from another company)."""
    pass
