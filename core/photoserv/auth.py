import hashlib
import os
from sqlalchemy.orm import Session
from sqlalchemy import select
from .data import Key
import secrets
from typing import Optional


SECRET_KEY_BASE = os.getenv("DATABASE_USER")


def does_key_exist(db: Session, api_key: str) -> bool:
    """
    Check if a regular API key exists (non-admin).
    """
    hashed_key = hashlib.sha512((SECRET_KEY_BASE + api_key).encode()).hexdigest()
    stmt = select(Key).where(Key.key == hashed_key, Key.admin == False)
    result = db.execute(stmt).scalars().first()
    return result is not None


def does_admin_key_exist(db: Session, api_key: str) -> bool:
    """
    Check if a specific admin API key exists.
    """
    hashed_key = hashlib.sha512((SECRET_KEY_BASE + api_key).encode()).hexdigest()
    stmt = select(Key).where(Key.key == hashed_key, Key.admin == True)
    result = db.execute(stmt).scalars().first()
    return result is not None


def does_any_key_exist(db: Session) -> bool:
    """
    Check if any API key (admin or not) exists.
    """
    stmt = select(Key)
    result = db.execute(stmt).scalars().first()
    return result is not None


def get_keys(db: Session) -> list[Key]:
    """
    Retrieve all keys from the database.
    """
    stmt = select(Key)
    result = db.execute(stmt).scalars().all()
    return result


def create_key(db: Session, admin: bool = False, name: Optional[str] = None) -> str:
    """
    Create a new API key (64 characters) and hash it with SHA-512.
    """
    new_key = secrets.token_hex(32)  # 64 characters
    hashed_key = hashlib.sha512((SECRET_KEY_BASE + new_key).encode()).hexdigest()
    new_key_entry = Key(key=hashed_key, admin=admin, name=name)
    db.add(new_key_entry)
    db.commit()
    db.refresh(new_key_entry)
    return new_key  # Return the unhashed key to the user


def delete_key(db: Session, key_or_id: str | int) -> bool:
    """
    Delete a key from the database by key or ID.
    """
    if isinstance(key_or_id, str):
        hashed_key = hashlib.sha512((SECRET_KEY_BASE + key_or_id).encode()).hexdigest()
        stmt = select(Key).where(Key.key == hashed_key)
    else:
        stmt = select(Key).where(Key.id == key_or_id)
    
    key_to_delete = db.execute(stmt).scalars().first()

    if key_to_delete:
        db.delete(key_to_delete)
        db.commit()
        return True
    return False
