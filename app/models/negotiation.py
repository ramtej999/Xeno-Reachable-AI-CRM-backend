from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
from decimal import Decimal
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.message import Message

class Negotiation(Base):
    __tablename__ = "negotiations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=True)
    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    negotiated_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    margin_floor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    current_offer: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    max_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, default=30.0)
    strategy: Mapped[str] = mapped_column(String(50), nullable=True, default="Balanced")
    status: Mapped[str] = mapped_column(String(50), nullable=True, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="negotiations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="negotiation", cascade="all, delete-orphan")