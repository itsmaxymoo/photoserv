import hashlib
import os
from sqlalchemy.orm import Session
from sqlalchemy import select
from .data import Key
import secrets
import hmac
from typing import Optional


MASTER_KEY_BASE = os.getenv("MASTER_KEY")


def hmac_sha512(key: str, msg: str) -> str:
    return hmac.new(key.encode(), msg.encode(), hashlib.sha512).hexdigest()


def does_key_exist(db: Session, api_key: str) -> bool:
    hashed_key = hmac_sha512(MASTER_KEY_BASE, api_key)
    stmt = select(Key).where(Key.key == hashed_key, Key.admin == False)
    result = db.execute(stmt).scalars().first()
    return result is not None


def does_admin_key_exist(db: Session, api_key: str) -> bool:
    hashed_key = hmac_sha512(MASTER_KEY_BASE, api_key)
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


def create_key(db: Session, admin: bool = False, name: Optional[str] = None) -> str:
    new_key = secrets.token_hex(32)  # 64 characters
    hashed_key = hmac_sha512(MASTER_KEY_BASE, new_key)
    new_key_entry = Key(key=hashed_key, admin=admin, name=name)
    db.add(new_key_entry)
    db.commit()
    db.refresh(new_key_entry)
    return new_key  # Return the unhashed key to the user


def delete_key(db: Session, key_or_id: str | int) -> bool:
    if isinstance(key_or_id, str):
        hashed_key = hmac_sha512(MASTER_KEY_BASE, key_or_id)
        stmt = select(Key).where(Key.key == hashed_key)
    else:
        stmt = select(Key).where(Key.id == key_or_id)

    key_to_delete = db.execute(stmt).scalars().first()

    if key_to_delete:
        db.delete(key_to_delete)
        db.commit()
        return True
    return False
