from __future__ import annotations
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.copilot_message import CopilotMessage

class CopilotConversation(Base):
    __tablename__ = "copilot_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

    messages: Mapped[List["CopilotMessage"]] = relationship("CopilotMessage", back_populates="conversation", cascade="all, delete-orphan")
