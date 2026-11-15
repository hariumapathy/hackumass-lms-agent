"""API routers (S02 stubs; replaced endpoint by endpoint by S11, S13, S20-S25, S32)."""

from fastapi import APIRouter

from app.api.routes import account, calendar, chat, connections, dashboard, files, study

api_router = APIRouter()
for _module in (account, connections, dashboard, chat, study, calendar, files):
    api_router.include_router(_module.router)
