"""
Pytest Test Fixtures and Dependency Overrides
Provides isolated test doubles for FastAPI authentication and database operations.
"""

import pytest
from typing import Optional
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_default_repository
from app.core.auth import (
    AuthUser,
    UserRole,
    authenticate_bearer_token,
    bearer_scheme,
)
from app.repositories.in_memory_task_repository import InMemoryTaskRepository

# Standard multi-tenant mock profiles matching task-c-database/seed.sql
MOCK_USERS = {
    "token_mgr_alpha": AuthUser(
        auth_user_id="auth_mgr_alpha_uid",
        profile_id="a1111111-1111-1111-1111-111111111111",
        company_id="a0000000-0000-0000-0000-000000000001",
        role=UserRole.MANAGER,
        email="alice.manager@acme.com",
        full_name="Alice Manager",
        access_token="token_mgr_alpha",
    ),
    "token_emp_alpha_1": AuthUser(
        auth_user_id="auth_emp_alpha_1_uid",
        profile_id="a2222222-2222-2222-2222-222222222222",
        company_id="a0000000-0000-0000-0000-000000000001",
        role=UserRole.EMPLOYEE,
        email="bob.developer@acme.com",
        full_name="Bob Developer",
        access_token="token_emp_alpha_1",
    ),
    "token_emp_alpha_2": AuthUser(
        auth_user_id="auth_emp_alpha_2_uid",
        profile_id="a3333333-3333-3333-3333-333333333333",
        company_id="a0000000-0000-0000-0000-000000000001",
        role=UserRole.EMPLOYEE,
        email="carol.designer@acme.com",
        full_name="Carol Designer",
        access_token="token_emp_alpha_2",
    ),
    "token_mgr_beta": AuthUser(
        auth_user_id="auth_mgr_beta_uid",
        profile_id="b1111111-1111-1111-1111-111111111111",
        company_id="b0000000-0000-0000-0000-000000000002",
        role=UserRole.MANAGER,
        email="david.manager@betarobotics.com",
        full_name="David Manager",
        access_token="token_mgr_beta",
    ),
    "token_emp_beta_1": AuthUser(
        auth_user_id="auth_emp_beta_1_uid",
        profile_id="b2222222-2222-2222-2222-222222222222",
        company_id="b0000000-0000-0000-0000-000000000002",
        role=UserRole.EMPLOYEE,
        email="eve.engineer@betarobotics.com",
        full_name="Eve Developer",
        access_token="token_emp_beta_1",
    ),
}


def mock_authenticate_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> AuthUser:
    """Mock authentication dependency for FastAPI test suites."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing: Authorization Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if token in MOCK_USERS:
        return MOCK_USERS[token]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or revoked authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@pytest.fixture
def test_repo():
    repo = InMemoryTaskRepository()
    repo.reset()
    return repo


@pytest.fixture(autouse=True)
def setup_dependencies(test_repo):
    """Wire mock repository and bearer token authentication for all tests."""
    app.dependency_overrides[get_default_repository] = lambda: test_repo

    # Also override authenticate_bearer_token with dependency on bearer_scheme
    def override_auth(
        credentials: Optional[HTTPAuthorizationCredentials] = pytest.importorskip("fastapi").Depends(bearer_scheme),
    ) -> AuthUser:
        return mock_authenticate_bearer_token(credentials)

    app.dependency_overrides[authenticate_bearer_token] = override_auth

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mgr_alpha_headers():
    return {"Authorization": "Bearer token_mgr_alpha"}


@pytest.fixture
def emp_alpha_headers():
    return {"Authorization": "Bearer token_emp_alpha_1"}


@pytest.fixture
def emp_alpha_2_headers():
    return {"Authorization": "Bearer token_emp_alpha_2"}


@pytest.fixture
def mgr_beta_headers():
    return {"Authorization": "Bearer token_mgr_beta"}


@pytest.fixture
def emp_beta_headers():
    return {"Authorization": "Bearer token_emp_beta_1"}
