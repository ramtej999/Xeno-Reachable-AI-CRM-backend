from sqlalchemy import String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.campaign import Campaign

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="events")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="events")