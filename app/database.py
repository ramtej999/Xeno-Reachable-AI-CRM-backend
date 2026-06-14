from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings
print("Database initialized successfully.")
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,   # Neon serverless requires no persistent pool
    connect_args={
        "connect_timeout": 30,
    }
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()