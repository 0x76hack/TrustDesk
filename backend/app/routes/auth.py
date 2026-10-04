import re
import time
from typing import Union, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app.services.audit_service import log_audit
import uuid
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    MfaChallengeResponse,
    MfaVerifyRequest,
    MfaSetupSendOtpRequest,
    MfaSetupVerifyOtpRequest,
    MfaResendLoginOtpRequest,
    PasswordChangeRequest,
    OAuthLoginRequest,
    UserProfileUpdate,
    PrimaryAdminSetupRequest,
)
from app.services.auth_service import (
    verify_password,
    hash_password,
    create_access_token,
    decode_token,
    get_user_by_username,
    get_user_by_id,
)
from app.services import otp_service
from app.services import oauth_service
from app.middleware.csrf import generate_csrf_token

router = APIRouter()

_login_attempts: Dict[str, list[float]] = {}
MAX_LOGIN_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    now = time.time()
    if len(_login_attempts) > 1000:
        stale_keys = [k for k, v in _login_attempts.items() if not v or (now - v[-1] >= LOGIN_WINDOW_SECONDS)]
        for k in stale_keys:
            _login_attempts.pop(k, None)

    history = _login_attempts.get(key, [])
    history = [t for t in history if now - t < LOGIN_WINDOW_SECONDS]
    if len(history) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again after 60 seconds.",
        )
    history.append(now)
    _login_attempts[key] = history


async def check_login_rate_limit_async(key: str) -> None:
    r = await otp_service.get_redis_client()
    if r:
        try:
            rkey = f"rate_limit:{key}"
            count = await r.incr(rkey)
            if count == 1:
                await r.expire(rkey, LOGIN_WINDOW_SECONDS)
            if count > MAX_LOGIN_ATTEMPTS:
                ttl = await r.ttl(rkey)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many authentication attempts. Please try again after {max(1, ttl)} seconds.",
                )
            return
        except HTTPException:
            raise
        except Exception:
            pass
    check_rate_limit(key)



def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if not re.search(r'[A-Z]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter.",
        )
    if not re.search(r'[a-z]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter.",
        )
    if not re.search(r'\d', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one numeric digit.",
        )
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>-_).",
        )


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get('/csrf-token')
async def get_csrf_token(request: Request):
    token = getattr(request.state, "csrf_token", None) or request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    return {"csrf_token": token}


@router.get('/setup-status')
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.role == "admin",
            ~User.email.endswith("@trustdesk.local"),
            User.mfa_setup_completed == True,
        )
    )
    admin_user = result.scalars().first()
    return {
        "is_initialized": admin_user is not None,
        "admin_username": admin_user.username if admin_user else None,
        "admin_email": admin_user.email if admin_user else None,
    }


@router.post('/setup-primary-admin', response_model=Union[LoginResponse, Dict[str, Any]])
async def setup_primary_admin(
    req: PrimaryAdminSetupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    clean_email = req.email.strip().lower()
    clean_username = req.username.strip().lower()
    clean_name = req.name.strip()

    if "@" not in clean_email or "." not in clean_email or clean_email.endswith("@trustdesk.local"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid operational email address is required for the primary administrator.",
        )

    validate_password_strength(req.password)

    existing_admin_res = await db.execute(
        select(User).where(
            User.role == "admin",
            ~User.email.endswith("@trustdesk.local"),
            User.mfa_setup_completed == True,
        )
    )
    if existing_admin_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Primary administrator account has already been initialized.",
        )

    if not req.code:
        otp_data = await otp_service.issue_otp(f"primary_admin_setup:{clean_email}", clean_email, req.phone)
        dev_code = otp_data.get("dev_code")
        msg = (
            f"Verification code dispatched to {clean_email}. Enter the 6-digit code to initialize the primary administrator account."
            if not dev_code
            else f"Verification code generated: {dev_code}. Enter this 6-digit code below to complete registration."
        )
        return {
            "otp_required": True,
            "email": clean_email,
            "expires_in_seconds": otp_data["expires_in_seconds"],
            "dev_code": dev_code,
            "message": msg,
        }

    clean_code = req.code.strip()
    await otp_service.verify_otp(f"primary_admin_setup:{clean_email}", clean_code)

    existing_user_res = await db.execute(
        select(User).where((User.username == clean_username) | (User.role == "admin"))
    )
    admin_user = existing_user_res.scalars().first()

    if admin_user:
        admin_user.name = clean_name
        admin_user.username = clean_username
        admin_user.email = clean_email
        admin_user.password_hash = hash_password(req.password)
        admin_user.phone = req.phone.strip() if req.phone else None
        admin_user.role = "admin"
        admin_user.mfa_setup_completed = True
        admin_user.is_primary_admin = True
        admin_user.is_active = True
    else:
        admin_user = User(
            id=str(uuid.uuid4()),
            name=clean_name,
            username=clean_username,
            email=clean_email,
            password_hash=hash_password(req.password),
            phone=req.phone.strip() if req.phone else None,
            role="admin",
            mfa_setup_completed=True,
            is_primary_admin=True,
            is_active=True,
        )
        db.add(admin_user)

    await log_audit(
        db=db,
        actor_id=admin_user.id,
        action="primary_admin_initialized",
        resource_type="user",
        resource_id=admin_user.id,
        outcome="success",
    )
    await db.commit()
    await db.refresh(admin_user)

    token = create_access_token({"sub": admin_user.id, "role": admin_user.role, "name": admin_user.name})
    set_auth_cookie(response, token)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(admin_user),
    )


@router.post('/login', response_model=Union[LoginResponse, MfaChallengeResponse])
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
    await check_login_rate_limit_async(f"login:{client_ip}:{req.username}")

    user = await get_user_by_username(req.username, db)
    if not user or not verify_password(req.password, user.password_hash):
        await log_audit(
            db=db,
            actor_id=req.username,
            action='login_failed',
            resource_type='user',
            resource_id=req.username,
            outcome='failure',
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid username or password',
        )

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    needs_setup = not user.mfa_setup_completed or user.email.endswith('@trustdesk.local')
    if needs_setup:
        setup_token = create_access_token({'sub': user.id, 'type': 'mfa_setup_pending', 'username': user.username})
        return MfaChallengeResponse(
            mfa_required=True,
            mfa_setup_required=True,
            mfa_token=setup_token,
            username=user.username,
            current_email=user.email,
            current_phone=user.phone,
            expires_in_seconds=120,
            message="First-time account setup required. Please enter your email address to initialize MFA.",
        )

    if req.code:
        clean_code = req.code.strip()
        await otp_service.verify_otp(f"login:{user.id}", clean_code)

        token = create_access_token({'sub': user.id, 'role': user.role, 'name': user.name})
        await log_audit(
            db=db,
            actor_id=user.id,
            action='login_success_mfa',
            resource_type='user',
            resource_id=user.id,
            outcome='success',
        )
        await db.commit()
        set_auth_cookie(response, token)
        return LoginResponse(
            access_token=token,
            token_type='bearer',
            user=UserResponse.model_validate(user),
        )

    otp_data = await otp_service.issue_otp(f"login:{user.id}", user.email, user.phone)
    mfa_token = create_access_token({'sub': user.id, 'type': 'mfa_pending', 'username': user.username})

    return MfaChallengeResponse(
        mfa_required=True,
        mfa_setup_required=False,
        mfa_token=mfa_token,
        username=user.username,
        current_email=user.email,
        current_phone=user.phone,
        expires_in_seconds=otp_data['expires_in_seconds'],
        message=otp_data['message'],
    )


@router.post('/oauth/login', response_model=MfaChallengeResponse)
async def oauth_login(req: OAuthLoginRequest, db: AsyncSession = Depends(get_db)):
    if req.state:
        oauth_service.verify_oauth_state(req.state)

    clean_email = req.email.strip().lower()

    stmt = select(User).where(User.email == clean_email)
    res = await db.execute(stmt)
    users = res.scalars().all()

    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ambiguous identity. Multiple accounts associated with '{clean_email}'. Please contact system administrator.",
        )

    user = users[0] if users else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No corporate account provisioned for identity '{clean_email}'. Contact system administrator.",
        )

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    needs_setup = not user.mfa_setup_completed or user.email.endswith('@trustdesk.local')
    if needs_setup:
        setup_token = create_access_token({'sub': user.id, 'type': 'mfa_setup_pending', 'username': user.username})
        return MfaChallengeResponse(
            mfa_required=True,
            mfa_setup_required=True,
            mfa_token=setup_token,
            username=user.username,
            current_email=user.email,
            current_phone=user.phone,
            expires_in_seconds=120,
            message=f"SSO Identity verified ({req.provider}). Complete MFA email setup to proceed.",
        )

    otp_data = await otp_service.issue_otp(f"login:{user.id}", user.email, user.phone)
    mfa_token = create_access_token({'sub': user.id, 'type': 'mfa_pending', 'username': user.username})

    return MfaChallengeResponse(
        mfa_required=True,
        mfa_setup_required=False,
        mfa_token=mfa_token,
        username=user.username,
        current_email=user.email,
        current_phone=user.phone,
        expires_in_seconds=otp_data['expires_in_seconds'],
        message=otp_data['message'],
    )


@router.post('/mfa/setup-send-otp')
async def mfa_setup_send_otp(req: MfaSetupSendOtpRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.setup_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Setup session expired. Please log in again.')

    if payload.get('type') != 'mfa_setup_pending':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid setup token.')

    user_id = payload.get('sub')
    clean_email = req.email.strip().lower()
    if '@' not in clean_email or '.' not in clean_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid email address format.')

    clean_phone = req.phone.strip() if req.phone else None
    otp_data = await otp_service.issue_otp(f"setup:{user_id}", clean_email, clean_phone)
    return otp_data


@router.post('/mfa/setup-verify-otp', response_model=LoginResponse)
async def mfa_setup_verify_otp(
    req: MfaSetupVerifyOtpRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(req.setup_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Setup session expired. Please log in again.')

    if payload.get('type') != 'mfa_setup_pending':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid setup token.')

    user_id = payload.get('sub')
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User account not found.')

    clean_code = req.code.strip()
    await otp_service.verify_otp(f"setup:{user_id}", clean_code)

    user.email = req.email.strip().lower()
    if req.phone and req.phone.strip():
        user.phone = req.phone.strip()
    user.mfa_setup_completed = True

    await log_audit(
        db=db,
        actor_id=user.id,
        action='mfa_setup_completed',
        resource_type='user',
        resource_id=user.id,
        outcome='success',
    )
    await db.commit()
    await db.refresh(user)

    token = create_access_token({'sub': user.id, 'role': user.role, 'name': user.name})
    set_auth_cookie(response, token)
    return LoginResponse(
        access_token=token,
        token_type='bearer',
        user=UserResponse.model_validate(user),
    )


@router.post('/mfa/resend-login-otp')
async def mfa_resend_login_otp(req: MfaResendLoginOtpRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.mfa_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Login session expired. Please log in again.')

    if payload.get('type') != 'mfa_pending':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid login token.')

    user_id = payload.get('sub')
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found.')

    otp_data = await otp_service.issue_otp(f"login:{user.id}", user.email, user.phone)
    return otp_data


@router.post('/mfa/verify', response_model=LoginResponse)
async def mfa_verify(
    req: MfaVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    clean_code = req.code.strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid MFA code. Verification code must be exactly 6 numeric digits.',
        )

    try:
        payload = decode_token(req.mfa_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='MFA session expired or invalid. Please authenticate again.',
        )

    if payload.get('type') != 'mfa_pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid MFA token format.',
        )

    user_id = payload.get('sub')
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    await otp_service.verify_otp(f"login:{user.id}", clean_code)

    token = create_access_token({'sub': user.id, 'role': user.role, 'name': user.name})

    await log_audit(
        db=db,
        actor_id=user.id,
        action='mfa_verified_login',
        resource_type='user',
        resource_id=user.id,
        outcome='success',
    )
    await db.commit()

    set_auth_cookie(response, token)
    return LoginResponse(
        access_token=token,
        token_type='bearer',
        user=UserResponse.model_validate(user),
    )


@router.post('/change-password')
async def change_password(
    req: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Current password does not match.',
        )

    new_pwd = req.new_password.strip()
    validate_password_strength(new_pwd)

    current_user.password_hash = hash_password(new_pwd)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action='password_changed',
        resource_type='user',
        resource_id=current_user.id,
        outcome='success',
    )
    await db.commit()

    return {'message': 'Password updated successfully.'}


@router.get('/me', response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put('/profile', response_model=UserResponse)
async def update_profile(
    profile_in: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if profile_in.name is not None and profile_in.name.strip():
        current_user.name = profile_in.name.strip()
    if profile_in.email is not None and profile_in.email.strip():
        current_user.email = profile_in.email.strip().lower()
    if profile_in.phone is not None:
        current_user.phone = profile_in.phone.strip() if profile_in.phone.strip() else None

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action='profile_updated',
        resource_type='user',
        resource_id=current_user.id,
        outcome='success',
    )
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
