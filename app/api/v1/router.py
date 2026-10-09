from fastapi import APIRouter

from app.api.v1 import auth, dashboard, gds, health, incidents, officers, stations, users, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(stations.router)
api_router.include_router(officers.router)
api_router.include_router(incidents.router)
api_router.include_router(gds.router)
api_router.include_router(dashboard.router)
api_router.include_router(ws.router)
