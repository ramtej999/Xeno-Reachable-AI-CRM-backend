from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class NegotiationCreate(BaseModel):
    customer_id: int
    product_name: str
    original_price: float
    margin_floor: float
    max_discount: Optional[float] = 30.0
    strategy: Optional[str] = "Balanced"

class MessageCreate(BaseModel):
    message: str

class NegotiateMessageRequest(BaseModel):
    message: str
    offer: float
    strategy: Optional[str] = "Balanced"

class MessageResponse(BaseModel):
    id: int
    negotiation_id: int
    sender: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NegotiationResponse(BaseModel):
    id: int
    customer_id: int
    product_name: str
    original_price: float
    negotiated_price: Optional[float] = None
    margin_floor: float
    current_offer: Optional[float] = None
    max_discount: Optional[float] = 30.0
    strategy: Optional[str] = "Balanced"
    status: str
    created_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)
