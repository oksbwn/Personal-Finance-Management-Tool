from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
import asyncio

from backend.app.core.config import settings
from backend.app.core.exceptions import http_exception_handler, generic_exception_handler
from backend.app.core.database import engine, Base, SessionLocal

# Routers
from backend.app.modules.auth.router import router as auth_router
from backend.app.modules.finance.routers import router as finance_router
from backend.app.modules.ingestion.router import router as ingestion_router
from backend.app.modules.ingestion.ai_router import router as ai_router

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
    
    # DB Creation (Dev only)
    Base.metadata.create_all(bind=engine)

    # --- Schema Migrations (Manual) ---
    with engine.connect() as conn:
        try:
            # Check if column exists in accounts table
            res = conn.execute(text("DESCRIBE accounts;")).fetchall()
            cols = [r[0] for r in res]
            if "credit_limit" not in cols:
                print("[Migration] Adding credit_limit to accounts table...")
                conn.execute(text("ALTER TABLE accounts ADD COLUMN credit_limit DECIMAL(15, 2);"))
                conn.commit()
                print("[Migration] Column added successfully.")
        except Exception as e:
            print(f"[Migration] Error checking/adding columns: {e}")

    # --- Background Tasks ---
    
    @application.on_event("startup")
    async def schedule_auto_sync():
        # Start Scheduler
        start_scheduler()
        
        async def run_auto_sync():
            while True:
                print("[AutoSync] Checking for scheduled syncs...")
                try:
                    # Create a new session for this thread
                    with SessionLocal() as db:
                        configs = db.query(ingestion_models.EmailConfiguration).filter(
                            ingestion_models.EmailConfiguration.is_active == True,
                            ingestion_models.EmailConfiguration.auto_sync_enabled == True
                        ).all()
                        
                        print(f"[AutoSync] Found {len(configs)} active configs.")
                        for config in configs:
                            print(f"[AutoSync] Syncing {config.email}...")
                            try:
                                EmailSyncService.sync_emails(
                                    db=db,
                                    tenant_id=config.tenant_id,
                                    config_id=config.id,
                                    imap_server=config.imap_server,
                                    email_user=config.email,
                                    email_pass=config.password,
                                    folder=config.folder,
                                    search_criterion='ALL'
                                )
                            except Exception as e:
                                print(f"[AutoSync] Error syncing {config.email}: {e}")
                except Exception as e:
                    print(f"[AutoSync] General Loop Error: {e}")
                
                # Sleep for 15 minutes (900 seconds)
                await asyncio.sleep(900)

        asyncio.create_task(run_auto_sync())

    @application.on_event("shutdown")
    async def stop_scheduler_event():
        stop_scheduler()

    return application

app = create_application()

@app.get("/")
def root():
    return {"message": "Welcome to Family Finance Platform API"}
