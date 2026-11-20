"""
Supabase Client Management
Provides connection-safe and concurrency-safe Supabase clients.
Never exposes or uses service_role / secret keys for user requests.
"""

from typing import Optional
from supabase import create_client, Client, ClientOptions
from app.config import settings
from app.core.exceptions import DomainException

_base_client: Optional[Client] = None


class SupabaseConfigurationError(DomainException):
    """Raised when Supabase credentials are missing or invalid."""
    pass


def get_base_supabase_client() -> Client:
    """
    Returns a singleton base Supabase client initialized with the publishable/anon key.
    Used for server-side auth token verification (auth.get_user(jwt)).
    """
    global _base_client
    if not settings.is_supabase_configured:
        raise SupabaseConfigurationError(
            "Supabase is not configured. Please define SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY) in .env."
        )

    if _base_client is None:
        _base_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_publishable_key,
        )
    return _base_client


def get_user_scoped_supabase_client(access_token: str) -> Client:
    """
    Creates a request-scoped Supabase client that forwards the user's JWT access token
    on all PostgREST database queries.
    
    Security Guarantee:
    - Concurrency-safe: each request receives an isolated client instance.
    - PostgreSQL Row Level Security (RLS) policies evaluate auth.uid() using this token.
    - Never uses service_role key; permissions are bounded by the caller's identity.
    """
    if not settings.is_supabase_configured:
        raise SupabaseConfigurationError(
            "Supabase is not configured. Please define SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env."
        )

    options = ClientOptions(
        headers={
            "Authorization": f"Bearer {access_token}",
        }
    )
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_publishable_key,
        options=options,
    )
