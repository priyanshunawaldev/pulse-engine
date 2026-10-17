from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis_dep
from app.core.security import check_rate_limit, decode_token, hash_api_key
from app.models.auth import APIKeyRecord

bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    def __init__(
        self,
        auth_type: str,
        identifier: str,
        details: dict[str, Any] | None = None,
    ):
        self.auth_type = auth_type  # "api_key" | "jwt"
        self.identifier = identifier
        self.details = details or {}


async def get_current_auth(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    bearer_creds: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
) -> AuthContext:
    """
    Dual Authentication dependency:
    Accepts either machine-to-machine API Key ('X-API-Key')
    or human/application JWT Bearer ('Authorization: Bearer ...').
    Applies per-principal Redis token bucket rate limiting.
    """
    auth_ctx: AuthContext | None = None

    # 1. Check API Key
    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        stmt = select(APIKeyRecord).where(
            APIKeyRecord.key_hash == key_hash,
            APIKeyRecord.is_active.is_(True),
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            auth_ctx = AuthContext(
                auth_type="api_key",
                identifier=f"apikey:{record.id}",
                details={"key_id": str(record.id), "name": record.name},
            )

    # 2. Check JWT Bearer
    if not auth_ctx and bearer_creds and bearer_creds.credentials:
        try:
            payload = decode_token(bearer_creds.credentials)
            sub = payload.get("sub")
            if sub and payload.get("type") == "access":
                auth_ctx = AuthContext(
                    auth_type="jwt",
                    identifier=f"jwt:{sub}",
                    details=payload,
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not auth_ctx:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication. Provide 'X-API-Key' or 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Apply Redis Token Bucket Rate Limiting
    is_allowed, remaining = await check_rate_limit(
        redis=redis,
        identifier=auth_ctx.identifier,
        capacity=settings.RATE_LIMIT_REQUESTS,
        refill_rate=settings.RATE_LIMIT_REQUESTS / settings.RATE_LIMIT_WINDOW_SECONDS,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Remaining capacity: {remaining} tokens.",
            headers={"Retry-After": "1"},
        )

    return auth_ctx
