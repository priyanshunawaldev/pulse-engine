import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenRequestSchema(BaseModel):
    client_id: str = Field(..., json_schema_extra={"example": "client_123456"})
    client_secret: str = Field(..., json_schema_extra={"example": "sec_abcdef123456"})


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequestSchema(BaseModel):
    refresh_token: str


class APIKeyCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "Stripe Integration Worker"})


class APIKeyResponseSchema(BaseModel):
    id: uuid.UUID
    name: str
    api_key: str
    created_at: datetime


class ClientCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "Fintech Dashboard Client"})


class ClientCreateResponseSchema(BaseModel):
    id: uuid.UUID
    client_id: str
    client_secret: str
    name: str
    created_at: datetime
