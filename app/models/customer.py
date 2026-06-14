from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import date, datetime
from decimal import Decimal
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.event import Event
    from app.models.negotiation import Negotiation

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(50), nullable=True)
    total_spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)
    segment: Mapped[str] = mapped_column(String(50), nullable=True)
    last_purchase: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="customer", cascade="all, delete-orphan")
    negotiations: Mapped[List["Negotiation"]] = relationship("Negotiation", back_populates="customer", cascade="all, delete-orphan")