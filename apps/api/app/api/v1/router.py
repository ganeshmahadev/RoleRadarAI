from fastapi import APIRouter

from app.api.v1 import companies, eures, health, jobs, match_runs, matches, resumes

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(companies.router)
api_router.include_router(eures.router)
api_router.include_router(jobs.router)
api_router.include_router(resumes.router)
api_router.include_router(matches.router)
api_router.include_router(match_runs.router)
