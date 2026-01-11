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
    # DB Creation (Dev only)
    from backend.app.core.database import engine, Base
    from sqlalchemy import text, inspect
    
    # Simple Auto-Migration: Add missing columns
    # We use a direct execution approach to avoid introspection issues
    # 1. Accounts Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN account_mask VARCHAR"))
            print("Detailed Migration Log: 'account_mask' column ADDED successfully.")
    except Exception as e:
        print(f"Detailed Migration Log: 'account_mask' likely exists. {e}")

    # 2. Transactions Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN type VARCHAR DEFAULT 'DEBIT'"))
            print("Detailed Migration Log: 'type' column ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'type' likely exists. {e}")

    # 3. Accounts Owner Name Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN owner_name VARCHAR"))
            print("Detailed Migration Log: 'owner_name' column ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'owner_name' likely exists. {e}")

    # 4. Accounts Balance Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN balance DECIMAL(15,2) DEFAULT 0"))
            print("Detailed Migration Log: 'balance' column ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'balance' likely exists. {e}")

    # 5. Accounts Verified Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN is_verified BOOLEAN DEFAULT TRUE"))
            print("Detailed Migration Log: 'is_verified' column ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'is_verified' likely exists. {e}")

    # 6. Transactions CreatedAt Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("Detailed Migration Log: 'created_at' column in transactions ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'created_at' in transactions likely exists. {e}")

    # 7. Category Rules Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS category_rules (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    keywords VARCHAR NOT NULL,
                    priority INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """))
            print("Detailed Migration Log: 'category_rules' table CREATED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'category_rules' table creation failed. {e}")

    # 8. Categories Migration (Ensure icon exists)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN icon VARCHAR DEFAULT '🏷️'"))
            print("Detailed Migration Log: 'icon' column in categories ADDED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'icon' in categories likely exists. {e}")

    # 9. Budgets Migration
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    amount_limit DECIMAL(15, 2) NOT NULL,
                    period VARCHAR DEFAULT 'MONTHLY',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """))
            print("Detailed Migration Log: 'budgets' table CREATED successfully.")
    except Exception as e:
         print(f"Detailed Migration Log: 'budgets' table creation failed. {e}")

    Base.metadata.create_all(bind=engine)

    return application

app = create_application()

@app.get("/")
def root():
    return {"message": "Welcome to Family Finance Platform API"}
