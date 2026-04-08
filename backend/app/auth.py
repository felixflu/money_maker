"""
Authentication service with password hashing and JWT token management.
"""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.schemas import TokenPayload

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(user_id: int) -> str:
    """Create a JWT access token for a user."""
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token for a user."""
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": REFRESH_TOKEN_TYPE,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None:
            return None
        return TokenPayload(sub=int(user_id), type=token_type)
    except (JWTError, ValueError):
        return None


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get a user by email address."""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, email: str, password: str) -> User:
    """Create a new user with hashed password."""
    hashed_password = get_password_hash(password)
    db_user = User(email=email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_password_reset_token(db: Session, user_id: int) -> str:
    """Create a password reset token for a user."""
    from app.models import PasswordResetToken
    import secrets

    # Generate a secure random token
    token = secrets.token_urlsafe(32)

    # Token expires in 1 hour
    expires_at = datetime.utcnow() + timedelta(hours=1)

    db_token = PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    return token


def get_password_reset_token(db: Session, token: str):
    """Get a password reset token by its value."""
    from app.models import PasswordResetToken

    return (
        db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    )


def is_token_valid(db_token) -> bool:
    """Check if a password reset token is valid (not expired and not used)."""
    if not db_token:
        return False
    if db_token.used_at is not None:
        return False
    if datetime.utcnow() > db_token.expires_at:
        return False
    return True


def mark_token_used(db: Session, db_token):
    """Mark a password reset token as used."""
    db_token.used_at = datetime.utcnow()
    db.commit()


def update_user_password(db: Session, user_id: int, new_password: str) -> User:
    """Update a user's password."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        db.refresh(user)
    return user
