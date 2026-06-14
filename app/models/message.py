from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.negotiation import Negotiation

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    negotiation_id: Mapped[int] = mapped_column(ForeignKey("negotiations.id"), nullable=True)
    sender: Mapped[str] = mapped_column(String(20), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    negotiation: Mapped["Negotiation"] = relationship("Negotiation", back_populates="messages")