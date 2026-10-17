import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_api_key,
)
from app.models.auth import APIKeyRecord, ClientRecord
from app.schemas.auth import (
    APIKeyCreateSchema,
    APIKeyResponseSchema,
    ClientCreateResponseSchema,
    ClientCreateSchema,
    RefreshTokenRequestSchema,
    TokenRequestSchema,
    TokenResponseSchema,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=TokenResponseSchema, summary="Obtain JWT access & refresh tokens")
async def obtain_token(
    payload: TokenRequestSchema,
    session: AsyncSession = Depends(get_db),
) -> TokenResponseSchema:
    """Client credentials flow: exchanges client_id and client_secret for JWT access and refresh tokens."""
    secret_hash = hashlib.sha256(payload.client_secret.encode("utf-8")).hexdigest()
    stmt = select(ClientRecord).where(
        ClientRecord.client_id == payload.client_id,
        ClientRecord.client_secret_hash == secret_hash,
        ClientRecord.is_active.is_(True),
    )
    result = await session.execute(stmt)
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": client.client_id, "name": client.name})
    refresh_token = create_refresh_token({"sub": client.client_id})

    return TokenResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponseSchema, summary="Refresh JWT access token")
async def refresh_access_token(
    payload: RefreshTokenRequestSchema,
) -> TokenResponseSchema:
    """Refreshes an expired access token using a valid refresh token."""
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token provided is not a refresh token.",
            )
        sub = decoded.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    access_token = create_access_token({"sub": sub})
    new_refresh_token = create_refresh_token({"sub": sub})

    return TokenResponseSchema(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/api-keys", response_model=APIKeyResponseSchema, status_code=status.HTTP_201_CREATED, summary="Generate API Key")
async def generate_api_key(
    payload: APIKeyCreateSchema,
    session: AsyncSession = Depends(get_db),
) -> APIKeyResponseSchema:
    """Generate a new API key. Raw key is returned once; subsequent lookups use SHA-256 hash."""
    raw_key = f"pk_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)

    record = APIKeyRecord(
        key_hash=key_hash,
        name=payload.name,
        is_active=True,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return APIKeyResponseSchema(
        id=record.id,
        name=record.name,
        api_key=raw_key,
        created_at=record.created_at,
    )


@router.post("/clients", response_model=ClientCreateResponseSchema, status_code=status.HTTP_201_CREATED, summary="Register OAuth Client")
async def register_client(
    payload: ClientCreateSchema,
    session: AsyncSession = Depends(get_db),
) -> ClientCreateResponseSchema:
    """Register a new OAuth client for client_credentials JWT authentication."""
    client_id = f"client_{secrets.token_hex(8)}"
    client_secret = f"sec_{secrets.token_urlsafe(24)}"
    secret_hash = hashlib.sha256(client_secret.encode("utf-8")).hexdigest()

    client = ClientRecord(
        client_id=client_id,
        client_secret_hash=secret_hash,
        name=payload.name,
        is_active=True,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)

    return ClientCreateResponseSchema(
        id=client.id,
        client_id=client.client_id,
        client_secret=client_secret,
        name=client.name,
        created_at=client.created_at,
    )
