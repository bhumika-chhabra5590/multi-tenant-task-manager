from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Multi-Tenant Task Management API"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False


settings = Settings()
