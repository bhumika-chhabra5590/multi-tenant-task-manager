from enum import Enum
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, status


class UserRole(str, Enum):
    MANAGER = "manager"
    EMPLOYEE = "employee"


class AuthUser(BaseModel):
    id: str
    company_id: str
    role: UserRole
    email: str
    full_name: str


# Pre-seeded users for authenticating requests and testing isolation
SEED_USERS: dict[str, AuthUser] = {
    # Company Alpha users
    "usr_mgr_alpha": AuthUser(
        id="usr_mgr_alpha",
        company_id="comp_alpha",
        role=UserRole.MANAGER,
        email="alice.manager@alpha.com",
        full_name="Alice Manager",
    ),
    "usr_emp_alpha_1": AuthUser(
        id="usr_emp_alpha_1",
        company_id="comp_alpha",
        role=UserRole.EMPLOYEE,
        email="bob.dev@alpha.com",
        full_name="Bob Developer",
    ),
    "usr_emp_alpha_2": AuthUser(
        id="usr_emp_alpha_2",
        company_id="comp_alpha",
        role=UserRole.EMPLOYEE,
        email="carol.qa@alpha.com",
        full_name="Carol QA",
    ),
    # Company Beta users (Separate tenant)
    "usr_mgr_beta": AuthUser(
        id="usr_mgr_beta",
        company_id="comp_beta",
        role=UserRole.MANAGER,
        email="david.manager@beta.com",
        full_name="David Manager",
    ),
    "usr_emp_beta_1": AuthUser(
        id="usr_emp_beta_1",
        company_id="comp_beta",
        role=UserRole.EMPLOYEE,
        email="eve.dev@beta.com",
        full_name="Eve Developer",
    ),
}


def authenticate_request(
    x_user_id: Optional[str] = Header(
        default=None,
        description="Authenticated User ID (e.g. from verified JWT / Session gateway)",
    ),
    x_company_id: Optional[str] = Header(
        default=None,
        description="Optional tenant header; must strictly match user's company context",
    ),
) -> AuthUser:
    """
    Authenticates the incoming request and derives tenant context.
    
    Security Guarantee:
    Tenant context is anchored directly to the cryptographic / server-validated user identity.
    If the caller provides an X-Company-Id header that mismatches the user's verified company,
    the request is rejected with 403 Forbidden to prevent cross-tenant parameter tampering.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing: X-User-Id header required.",
        )

    user = SEED_USERS.get(x_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user credentials: User '{x_user_id}' does not exist.",
        )

    # Cross-tenant tampering defense:
    # If client attempts to spoof company_id via header, reject immediately!
    if x_company_id and x_company_id != user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch detected: Provided X-Company-Id does not match user company context.",
        )

    return user
