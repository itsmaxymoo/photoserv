from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional


# Base class for ORM models
Base = declarative_base()


class Key(Base):
    __tablename__ = "keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<Key(id={self.id}, key={self.key}, admin={self.admin}, name={self.name})>"
