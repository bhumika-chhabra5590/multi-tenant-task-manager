"""
Supabase Authentication & Multi-Tenant Authorization Context
Enforces real JWT verification via Supabase Auth and derives identity from public.users.
No hardcoded users. No unverified JWT decoding. No X-User-Id / X-Company-Id headers.
"""

import logging
from enum import Enum
from typing import Optional
import httpx
from pydantic import BaseModel, ConfigDict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.supabase_client import (
    get_base_supabase_client,
    get_user_scoped_supabase_client,
    SupabaseConfigurationError,
)

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    MANAGER = "manager"
    EMPLOYEE = "employee"


class AuthUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    auth_user_id: str   # Supabase Auth UID (auth.users.id / auth.uid())
    profile_id: str     # Application Profile UUID (public.users.id)
    company_id: str     # Tenant UUID (public.users.company_id)
    role: UserRole      # Application Role ('manager' | 'employee')
    email: str
    full_name: str
    access_token: str   # Verified Bearer JWT used for scoped database queries

    @property
    def id(self) -> str:
        """Returns the internal profile_id used as creator and assignee reference."""
        return self.profile_id


# Register HTTP Bearer in OpenAPI so Swagger UI displays the "Authorize" button
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Supabase Auth Access Token (Bearer JWT)",
)


def authenticate_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    """
    Authenticates incoming requests using Supabase Auth JWT and derives the trusted
    tenant profile directly from public.users.
    
    Security Workflow:
    1. Rejects missing Bearer tokens with HTTP 401.
    2. Validates JWT signature, expiration, and revocation via Supabase auth.get_user(jwt).
    3. Obtains verified auth.users.id.
    4. Looks up public.users matching auth_user_id = auth.users.id.
    5. Establishes the single source of truth for company_id and role from the database.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing: Authorization Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing: Empty Bearer token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        supabase = get_base_supabase_client()
    except SupabaseConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # 1. Cryptographic Server-Side Verification via Supabase Auth
    try:
        auth_response = supabase.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or revoked authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        auth_user_id = auth_response.user.id
        auth_email = auth_response.user.email or ""
    except HTTPException:
        raise
    except (httpx.ConnectError, httpx.TimeoutException) as net_exc:
        logger.error("Upstream connection error reaching Supabase Auth: %s", net_exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Look up application profile in public.users using user-scoped client
    try:
        user_client = get_user_scoped_supabase_client(token)
        result = (
            user_client.table("users")
            .select("id, company_id, role, email, full_name, auth_user_id")
            .eq("auth_user_id", auth_user_id)
            .execute()
        )
    except Exception as db_exc:
        logger.error("Database query failed while retrieving user profile: %s", db_exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred while retrieving user profile.",
        )

    if not result.data or len(result.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user is not mapped to an active organization profile in the database.",
        )

    profile = result.data[0]

    try:
        user_role = UserRole(profile["role"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile has an invalid or unrecognized role.",
        )

    return AuthUser(
        auth_user_id=auth_user_id,
        profile_id=str(profile["id"]),
        company_id=str(profile["company_id"]),
        role=user_role,
        email=profile.get("email") or auth_email,
        full_name=profile.get("full_name", ""),
        access_token=token,
    )
