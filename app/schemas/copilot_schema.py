from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class CopilotRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

class CopilotCancelRequest(BaseModel):
    conversation_id: int

class CopilotResponse(BaseModel):
    response: str
    conversation_id: int
    title: str

class CopilotConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"

class CopilotMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CopilotConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[CopilotMessageResponse]] = []

    model_config = ConfigDict(from_attributes=True)