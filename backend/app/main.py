from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
import asyncio

from backend.app.core.config import settings
from backend.app.core.exceptions import http_exception_handler, generic_exception_handler
from backend.app.core.database import engine, Base, SessionLocal
from backend.app.core.migration import run_auto_migrations

# Routers
from backend.app.modules.auth.router import router as auth_router
from backend.app.modules.finance.routers import router as finance_router
from backend.app.modules.ingestion.router import router as ingestion_router
from backend.app.modules.ingestion.ai_router import router as ai_router
from backend.app.modules.mobile.router import router as mobile_router

# Background Tasks
from backend.app.modules.ingestion.email_sync import EmailSyncService
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.core.scheduler import start_scheduler, stop_scheduler

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    # Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(Exception, generic_exception_handler)

    # Routers
    application.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
    application.include_router(finance_router, prefix=f"{settings.API_V1_STR}/finance", tags=["finance"])
    application.include_router(ingestion_router, prefix=f"{settings.API_V1_STR}/ingestion", tags=["ingestion"])
    application.include_router(ai_router, prefix=f"{settings.API_V1_STR}/ingestion", tags=["ai"])
    application.include_router(mobile_router, prefix=f"{settings.API_V1_STR}/mobile", tags=["mobile"])
    
    
    # DB Creation (Dev only - migrations removed, use fresh schema.sql for setup)
    # Checks for existing tables.
    
    # Run Auto-Migrations (DuckDB Schema Evolution)
    run_auto_migrations(engine)

    Base.metadata.create_all(bind=engine)

    # --- Background Tasks ---
    
    @application.on_event("startup")
    async def startup_event():
        # Start Scheduler (Handles both recurring checks and email auto-sync)
        start_scheduler()

    @application.on_event("shutdown")
    async def stop_scheduler_event():
        stop_scheduler()

    return application

app = create_application()

@app.get("/")
def root():
    return {"message": "Welcome to WealthFam API"}
