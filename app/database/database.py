
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# SQLite requires this setting for FastAPI applications.
connect_args = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


# Create the database engine.
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug
)


# Create the session factory.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# Base class for all database models.
class Base(DeclarativeBase):
    pass


# Provide a database session to API routes.
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
