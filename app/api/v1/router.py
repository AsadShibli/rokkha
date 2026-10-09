from fastapi import APIRouter

from app.api.v1 import auth, health, officers, stations, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(stations.router)
api_router.include_router(officers.router)
