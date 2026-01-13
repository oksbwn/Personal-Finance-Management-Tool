from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.exceptions import http_exception_handler, generic_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

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
    from backend.app.modules.auth.router import router as auth_router
    from backend.app.modules.finance.router import router as finance_router
    from backend.app.modules.ingestion.router import router as ingestion_router
    
    application.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
    application.include_router(finance_router, prefix=f"{settings.API_V1_STR}/finance", tags=["finance"])
    application.include_router(ingestion_router, prefix=f"{settings.API_V1_STR}/ingestion", tags=["ingestion"])
    
    # DB Creation (Dev only)
    from backend.app.core.database import engine, Base
    Base.metadata.create_all(bind=engine)

    # --- Background Tasks ---
    import asyncio
    from backend.app.modules.ingestion.email_sync import EmailSyncService
    from backend.app.modules.ingestion import models as ingestion_models
    from backend.app.modules.ingestion.services import IngestionService # Indirectly needed
    from backend.app.core.database import SessionLocal
    
    @application.on_event("startup")
    async def schedule_auto_sync():
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

    return application

app = create_application()

@app.get("/")
def root():
    return {"message": "Welcome to Family Finance Platform API"}
