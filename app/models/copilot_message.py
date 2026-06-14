from __future__ import annotations
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.copilot_conversation import CopilotConversation

class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False)
    sender: Mapped[str] = mapped_column(String(50), nullable=False)  # 'user' or 'assistant'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    conversation: Mapped["CopilotConversation"] = relationship("CopilotConversation", back_populates="messages")
