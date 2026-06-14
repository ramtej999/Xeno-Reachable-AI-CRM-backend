from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    name: str
    org: Optional[str] = None
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: Optional[str] = None
    org: Optional[str] = None
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    org: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
