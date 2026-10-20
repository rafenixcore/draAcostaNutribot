from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Doctor, TokenBlacklist

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


async def _is_token_blacklisted(token: str, db: AsyncSession) -> bool:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == token_hash)
    )
    return result.scalar_one_or_none() is not None


async def get_current_doctor(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> Doctor:
    if await _is_token_blacklisted(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    try:
        doctor_id = int(decode_access_token(token))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if doctor is None or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or unknown user",
        )
    if doctor.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )
    return doctor


async def get_current_active_doctor(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> Doctor:
    if await _is_token_blacklisted(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    try:
        doctor_id = int(decode_access_token(token))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if doctor is None or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or unknown user",
        )
    return doctor


async def get_current_admin(
    doctor: Doctor = Depends(get_current_doctor),
) -> Doctor:
    if doctor.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return doctor
