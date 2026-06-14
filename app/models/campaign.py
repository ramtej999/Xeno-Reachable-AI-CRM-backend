from __future__ import annotations
from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from decimal import Decimal
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.event import Event

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=True)
    audience_size: Mapped[int] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    launch_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    target_segment: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    events: Mapped[List["Event"]] = relationship("Event", back_populates="campaign", cascade="all, delete-orphan")