from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.products import router as products_router
from app.api.v1.prices import router as prices_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.search import router as search_router
from app.api.v1.chat import router as chat_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(products_router)
api_v1_router.include_router(prices_router)
api_v1_router.include_router(subscriptions_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(recommendations_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(chat_router)
