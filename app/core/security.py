import hashlib
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from redis.asyncio import Redis

from app.core.config import settings

# Lua Script for Atomic Token Bucket Rate Limiting
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local last_tokens = tonumber(redis.call('HGET', key, 'tokens'))
local last_refreshed = tonumber(redis.call('HGET', key, 'last_refreshed'))

if last_tokens == nil then
    last_tokens = capacity
    last_refreshed = now
end

local delta = math.max(0, now - last_refreshed)
local filled_tokens = math.min(capacity, last_tokens + (delta * refill_rate))

if filled_tokens >= requested then
    local new_tokens = filled_tokens - requested
    redis.call('HSET', key, 'tokens', tostring(new_tokens), 'last_refreshed', tostring(now))
    redis.call('EXPIRE', key, math.ceil(capacity / math.max(refill_rate, 1)) * 2)
    return {1, math.floor(new_tokens)}
else
    redis.call('HSET', key, 'tokens', tostring(filled_tokens), 'last_refreshed', tostring(now))
    redis.call('EXPIRE', key, math.ceil(capacity / math.max(refill_rate, 1)) * 2)
    return {0, math.floor(filled_tokens)}
end
"""


def hash_api_key(api_key: str) -> str:
    """Hash raw API key using SHA-256 for secure storage."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create short-lived JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create longer-lived JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def check_rate_limit(
    redis: Redis,
    identifier: str,
    capacity: int | None = None,
    refill_rate: float | None = None,
    requested: int = 1,
) -> tuple[bool, int]:
    """
    Check and consume tokens using Redis Token Bucket.
    Returns (is_allowed, remaining_tokens).
    """
    cap = capacity or settings.RATE_LIMIT_REQUESTS
    rate = refill_rate or (settings.RATE_LIMIT_REQUESTS / settings.RATE_LIMIT_WINDOW_SECONDS)
    now = time.time()
    key = f"ratelimit:{identifier}"

    result = await redis.eval(
        LUA_TOKEN_BUCKET,
        1,
        key,
        cap,
        rate,
        now,
        requested,
    )
    allowed = bool(result[0] == 1)
    remaining = int(result[1])
    return allowed, remaining
