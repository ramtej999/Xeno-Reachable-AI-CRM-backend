from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime

class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True, nullable=False)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str] = mapped_column(String, nullable=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True, nullable=False)
