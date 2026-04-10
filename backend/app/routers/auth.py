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
    create_password_reset_token,
    get_password_reset_token,
    is_token_valid,
    mark_token_used,
    update_user_password,
)
from app.schemas import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
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


@router.post(
    "/password-reset-request",
    response_model=PasswordResetResponse,
    summary="Request password reset",
    description="Request a password reset email. Sends a reset token to the user's email.",
)
async def password_reset_request(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """
    Request a password reset.

    - **email**: Registered email address

    Always returns success to prevent email enumeration attacks.
    """
    user = get_user_by_email(db, reset_request.email)

    if user:
        # Create password reset token
        token = create_password_reset_token(db, user.id)

        # TODO: Send email with reset link
        # For now, we just log/print the token (in production, send via email)
        # In a real implementation, this would send an email with:
        # f"{FRONTEND_URL}/reset-password?token={token}"

    # Always return the same response to prevent email enumeration
    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


@router.post(
    "/password-reset",
    response_model=PasswordResetResponse,
    summary="Reset password",
    description="Reset password using a valid reset token.",
)
async def password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """
    Reset password using a reset token.

    - **token**: Password reset token received via email
    - **new_password**: New password (min 8 characters)

    Returns success message if password was reset.
    """
    # Get the token from database
    db_token = get_password_reset_token(db, reset_data.token)

    # Check if token is valid
    if not is_token_valid(db_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update the user's password
    user = update_user_password(db, db_token.user_id, reset_data.new_password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Mark token as used
    mark_token_used(db, db_token)

    return {"message": "Password has been reset successfully"}
