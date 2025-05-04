from sqlalchemy.orm import Session
from sqlalchemy import select
from .data import Key
import secrets
from typing import Optional


def does_key_exist(db: Session, api_key: str) -> bool:
    """
    Check if a regular API key exists (non-admin).
    """
    stmt = select(Key).where(Key.key == api_key, Key.admin == False)
    result = db.execute(stmt).scalars().first()
    return result is not None


def does_admin_key_exist(db: Session, api_key: str) -> bool:
    """
    Check if a specific admin API key exists.
    """
    stmt = select(Key).where(Key.key == api_key, Key.admin == True)
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
    Create a new API key (64 characters).
    """
    new_key = secrets.token_hex(32)  # 64 characters
    new_key_entry = Key(key=new_key, admin=admin, name=name)
    db.add(new_key_entry)
    db.commit()
    db.refresh(new_key_entry)
    return new_key


def delete_key(db: Session, key_or_id: str | int) -> bool:
    """
    Delete a key from the database by key or ID.
    """
    if isinstance(key_or_id, str):
        stmt = select(Key).where(Key.key == key_or_id)
    else:
        stmt = select(Key).where(Key.id == key_or_id)
    
    key_to_delete = db.execute(stmt).scalars().first()

    if key_to_delete:
        db.delete(key_to_delete)
        db.commit()
        return True
    return False
