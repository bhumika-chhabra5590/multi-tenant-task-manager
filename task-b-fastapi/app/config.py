import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env from project root if present
root_dir = Path(__file__).resolve().parent.parent.parent
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()


class Settings(BaseModel):
    app_name: str = "Multi-Tenant Task Management API"
    app_version: str = "2.0.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1")

    app_env: str = os.getenv("APP_ENV", "development")
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_publishable_key: str = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )

    @property
    def is_supabase_configured(self) -> bool:
        """Returns True only if real, non-placeholder Supabase credentials are configured."""
        if not self.supabase_url or not self.supabase_publishable_key:
            return False
        if "your-project" in self.supabase_url or "your-supabase" in self.supabase_publishable_key:
            return False
        return True


settings = Settings()
