"""
Authentication routes for user registration and login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    create_user,
)
from app.schemas import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest,
    RefreshTokenRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)

    Returns the created user (without password).
    """
    # Check if user already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = create_user(db, email=user_data.email, password=user_data.password)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login user",
    description="Authenticate user and return access and refresh tokens.",
)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login with email and password.

    - **email**: Registered email address
    - **password**: User password

    Returns access token and refresh token.
    """
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/login/form",
    response_model=Token,
    summary="Login user (OAuth2 form)",
    description="OAuth2 compatible login endpoint for form-based authentication.",
)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login with OAuth2 password flow (form data).

    - **username**: Email address (OAuth2 uses 'username' field)
    - **password**: User password

    Returns access token and refresh token.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token.",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Refresh access token.

    - **refresh_token**: Valid refresh token

    Returns new access token and refresh token.
    """
    payload = decode_token(refresh_data.refresh_token)
    if not payload or payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.models import User

    user = db.query(User).filter(User.id == payload.sub).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }
