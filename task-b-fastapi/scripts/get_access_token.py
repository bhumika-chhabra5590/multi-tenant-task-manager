#!/usr/bin/env python3
"""
CLI Helper: Obtain Supabase Auth Access Token for Manual & Swagger API Testing.
Authenticates against Supabase Auth using the publishable/anon key.
Never saves passwords or tokens to disk. Never uses a service_role key.
"""

import os
import sys
import getpass
from pathlib import Path

# Add project root to sys.path so app imports work
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

# Load .env from project root
env_path = backend_dir.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from supabase import create_client


def main():
    print("=" * 70)
    print("Supabase Auth Token Generator (FastAPI / Swagger UI)")
    print("=" * 70)

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )

    if not supabase_url or not supabase_key or "your-project" in supabase_url:
        print("\n[ERROR] Supabase credentials not found or unconfigured in .env.")
        print("Please set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in your .env file.\n")
        sys.exit(1)

    # Prompt for credentials
    email = input("Enter Supabase Auth Email: ").strip()
    if not email:
        print("[ERROR] Email cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Enter Supabase Auth Password: ")
    if not password:
        print("[ERROR] Password cannot be empty.")
        sys.exit(1)

    print("\nAuthenticating with Supabase Auth...")

    try:
        supabase = create_client(supabase_url=supabase_url, supabase_key=supabase_key)
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        if not response or not response.session:
            print("\n[ERROR] Sign-in failed: No active session returned.")
            sys.exit(1)

        token = response.session.access_token
        user = response.user

        print("\n" + "=" * 70)
        print("AUTHENTICATION SUCCESSFUL!")
        print("=" * 70)
        print(f"User Email   : {user.email}")
        print(f"Auth UID     : {user.id}")
        print("-" * 70)
        print("BEARER ACCESS TOKEN (Copy and paste into Swagger UI 'Authorize' modal):")
        print("-" * 70)
        print(token)
        print("=" * 70)
        print("\nNOTE: This token is displayed in memory only and has NOT been saved to disk.")

    except Exception as exc:
        print(f"\n[ERROR] Authentication failed: {str(exc)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
