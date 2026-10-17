from fastapi import APIRouter

from app.api.v1.endpoints import accounts, auth, health, transactions, webhooks

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(accounts.router)
api_v1_router.include_router(transactions.router)
api_v1_router.include_router(webhooks.router)

# Health router is attached at root level and v1
api_v1_router.include_router(health.router)
