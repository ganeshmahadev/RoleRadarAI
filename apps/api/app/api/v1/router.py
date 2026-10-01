from fastapi import APIRouter

from app.api.v1 import companies, eures, health, jobs, resumes

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(companies.router)
api_router.include_router(eures.router)
api_router.include_router(jobs.router)
api_router.include_router(resumes.router)
