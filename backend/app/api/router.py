from fastapi import APIRouter

from app.api import admin, auth, dashboard, diets, doctors, health, intake_links, patients, trash

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(intake_links.router, prefix="/intake-links", tags=["intake-links"])
api_router.include_router(diets.router, prefix="/diets", tags=["diets"])
api_router.include_router(trash.router, tags=["trash"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
