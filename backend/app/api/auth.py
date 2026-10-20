import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_doctor, oauth2_scheme
from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.models import Doctor, PasswordResetToken, TokenBlacklist, utcnow
from app.schemas import (
    DoctorCreate,
    DoctorOut,
    ForgotPasswordRequest,
    PasswordChange,
    ResetPasswordRequest,
    Token,
    VerifyTokenResponse,
)
from app.services.auth_email_service import send_password_reset_email

router = APIRouter()


@router.get("/registration-open")
async def registration_open(db: AsyncSession = Depends(get_db)):
    if settings.is_production:
        return {"open": False}
    count = (
        await db.execute(select(func.count()).select_from(Doctor))
    ).scalar_one()
    return {"open": count == 0}


@router.post("/register", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
async def register_doctor(body: DoctorCreate, db: AsyncSession = Depends(get_db)):
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled.",
        )
    existing = (
        await db.execute(select(func.count()).select_from(Doctor))
    ).scalar_one()
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed: a doctor account already exists.",
        )
    doctor = Doctor(
        full_name=body.full_name,
        email=body.email.lower().strip(),
        phone=body.phone,
        hashed_password=get_password_hash(body.password),
        role="doctor",
        must_change_password=False,
    )
    db.add(doctor)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        ) from None
    await db.refresh(doctor)
    return doctor


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.email == form_data.username.lower().strip())
    )
    doctor = result.scalar_one_or_none()
    if doctor is None or not verify_password(form_data.password, doctor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account",
        )
    # Portal validation
    portal = form_data.client_secret or "doctor"
    if portal not in ("admin", "doctor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portal value",
        )
    if portal == "admin" and doctor.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to administrators",
        )
    if portal == "doctor" and doctor.role not in ("doctor",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to doctors",
        )
    role = doctor.role or "doctor"
    must_change_password = bool(doctor.must_change_password)
    token = create_access_token(
        str(doctor.id),
        {
            "role": role,
            "must_change_password": must_change_password,
        },
    )
    return Token(
        access_token=token,
        role=role,
        must_change_password=must_change_password,
    )


@router.post("/change-password", response_model=Token)
async def change_password(
    body: PasswordChange,
    doctor: Doctor = Depends(get_current_active_doctor),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, doctor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if verify_password(body.new_password, doctor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    doctor.hashed_password = get_password_hash(body.new_password)
    doctor.must_change_password = False
    doctor.updated_at = utcnow()
    await db.commit()
    await db.refresh(doctor)
    role = doctor.role or "doctor"
    token = create_access_token(
        str(doctor.id),
        {
            "role": role,
            "must_change_password": False,
        },
    )
    return Token(access_token=token, role=role, must_change_password=False)


@router.post("/refresh")
async def refresh(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    token_hash = sha256(token.encode()).hexdigest()
    # Check blacklist
    result = await db.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == token_hash)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    # Decode current token
    try:
        doctor_id = int(decode_access_token(token))
    except (ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    # Verify doctor still exists and is active
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if not doctor or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found or inactive",
        )
    # Blacklist old token
    import jwt as _jwt
    try:
        payload = _jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM], options={"verify_exp": False})
        exp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else utcnow()
    except Exception:
        expires_at = utcnow()
    blacklisted = TokenBlacklist(jti=token_hash, expires_at=expires_at)
    db.add(blacklisted)

    # Issue new token
    role = doctor.role or "doctor"
    new_token = create_access_token(
        str(doctor.id),
        {"role": role, "must_change_password": doctor.must_change_password},
    )
    await db.commit()
    return Token(access_token=new_token, role=role, must_change_password=doctor.must_change_password)


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    token_hash = sha256(token.encode()).hexdigest()
    # Check if already blacklisted
    result = await db.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == token_hash)
    )
    if result.scalar_one_or_none():
        return {"ok": True}
    # Decode to get expiration
    from datetime import timezone
    try:
        import jwt
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        exp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else utcnow()
    except Exception:
        expires_at = utcnow()
    blacklisted = TokenBlacklist(jti=token_hash, expires_at=expires_at)
    db.add(blacklisted)
    await db.commit()
    return {"ok": True}


@router.post("/forgot-password")
@limiter.limit("2/10minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    # Always respond same way regardless of whether email exists (prevents enumeration)
    result = await db.execute(
        select(Doctor).where(Doctor.email == body.email.lower().strip())
    )
    doctor = result.scalar_one_or_none()

    if doctor is not None:
        # Invalidate any existing unused tokens for this doctor
        existing = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.doctor_id == doctor.id,
                PasswordResetToken.used.is_(False),
                PasswordResetToken.expires_at > utcnow(),
            )
        )
        for tok in existing.scalars():
            tok.used = True

        token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            doctor_id=doctor.id,
            token=token,
            expires_at=utcnow() + timedelta(minutes=30),
        )
        db.add(reset_token)
        await db.commit()

        reset_link = f"{settings.APP_URL}/reset-password?token={token}"
        # Fire email in thread to avoid blocking event loop
        asyncio.ensure_future(
            asyncio.to_thread(send_password_reset_email, doctor.email, doctor.full_name, reset_link)
        )

    return {"ok": True, "message": "Si el correo existe, recibirás instrucciones"}


@router.get("/verify-reset-token", response_model=VerifyTokenResponse)
async def verify_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None or reset_token.used or reset_token.expires_at <= utcnow():
        return VerifyTokenResponse(valid=False)

    doctor = await db.get(Doctor, reset_token.doctor_id)
    if doctor is None or not doctor.is_active:
        return VerifyTokenResponse(valid=False)

    return VerifyTokenResponse(valid=True, email=doctor.email)


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == body.token)
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None or reset_token.used or reset_token.expires_at <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    doctor = await db.get(Doctor, reset_token.doctor_id)
    if doctor is None or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    doctor.hashed_password = get_password_hash(body.new_password)
    doctor.must_change_password = False
    doctor.updated_at = utcnow()
    reset_token.used = True
    await db.commit()

    return {"ok": True}
