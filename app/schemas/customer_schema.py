from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional

class CustomerCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    city: Optional[str] = None
    total_spend: Optional[float] = 0.0
    segment: Optional[str] = "New Customers"
    last_purchase: Optional[date] = None

class CustomerResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    total_spend: Optional[float] = 0.0
    segment: Optional[str] = None
    last_purchase: Optional[date] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)