from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from . import *

# Database connection configuration
__engine = create_engine(f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}", echo=False, future=True)
__SessionLocal = sessionmaker(bind=__engine, autoflush=False, autocommit=False)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = __SessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_db():
    """Creates all tables defined in the ORM models."""
    from .data import Base  # Make sure Base and models are imported
    Base.metadata.create_all(bind=__engine)