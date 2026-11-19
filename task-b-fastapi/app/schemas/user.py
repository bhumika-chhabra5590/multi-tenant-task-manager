from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.core.auth import UserRole


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    email: str
    full_name: str
    role: UserRole
    created_at: datetime
