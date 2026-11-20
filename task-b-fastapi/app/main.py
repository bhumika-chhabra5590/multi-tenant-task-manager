from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import tasks
from app.config import settings
from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ForbiddenActionError,
    InvalidStateTransitionError,
    TenantViolationError,
)
from app.core.supabase_client import SupabaseConfigurationError
from app.repositories.supabase_task_repository import DatabaseOperationError

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Production-grade Multi-Tenant Task Management REST API integrated with "
        "Supabase Authentication, PostgreSQL, and Row Level Security (RLS)."
    ),
)

# CORS Middleware restricted to documented local development origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Exception Handlers mapping domain exceptions to standard HTTP error codes
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.message, "error_type": "entity_not_found"},
    )


@app.exception_handler(ForbiddenActionError)
async def forbidden_action_handler(request: Request, exc: ForbiddenActionError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": exc.message, "error_type": "forbidden"},
    )


@app.exception_handler(TenantViolationError)
async def tenant_violation_handler(request: Request, exc: TenantViolationError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": exc.message, "error_type": "tenant_violation"},
    )


@app.exception_handler(InvalidStateTransitionError)
async def invalid_state_transition_handler(
    request: Request, exc: InvalidStateTransitionError
):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "error_type": "invalid_state_transition"},
    )


@app.exception_handler(BusinessRuleViolationError)
async def business_rule_violation_handler(
    request: Request, exc: BusinessRuleViolationError
):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "error_type": "business_rule_violation"},
    )


@app.exception_handler(DatabaseOperationError)
async def database_operation_error_handler(
    request: Request, exc: DatabaseOperationError
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.message, "error_type": "database_error"},
    )


@app.exception_handler(SupabaseConfigurationError)
async def supabase_configuration_error_handler(
    request: Request, exc: SupabaseConfigurationError
):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": exc.message, "error_type": "service_unavailable"},
    )


# Include routes both under /tasks (per assignment spec) and /api/v1/tasks (versioned)
app.include_router(tasks.router)
app.include_router(tasks.router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "supabase_configured": settings.is_supabase_configured,
        "environment": settings.app_env,
    }
