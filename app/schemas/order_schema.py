from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class OrderCreate(BaseModel):
    customer_id: int
    order_number: str
    product_name: str
    category: Optional[str] = None
    quantity: Optional[int] = 1
    unit_price: float
    total_amount: float
    order_status: Optional[str] = "Completed"
    purchase_date: datetime

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    order_number: str
    product_name: str
    category: Optional[str] = None
    quantity: Optional[int] = 1
    unit_price: float
    total_amount: float
    order_status: Optional[str] = None
    purchase_date: datetime
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
