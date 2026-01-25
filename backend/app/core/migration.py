from sqlalchemy import text
from sqlalchemy.engine import Engine

def run_auto_migrations(engine: Engine):
    """
    Runs auto-migration logic to ensure the database schema matches the code expectations.
    This is designed for DuckDB which doesn't have robust Alembic support for all operations.
    
    NOTE: This function blocks and may raise exceptions if the DB is locked.
    The service manager (Systemd/Docker) should handle restarts in case of Lock errors.
    """
    try:
        with engine.connect() as connection:
            print("Running auto-migration for mobile features...")
            
            # Helper to add columns safely
            def safe_add_column(table, col, type_def):
                try:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {type_def}"))
                    print(f"Migrated: added {col} to {table}")
                except Exception as e:
                    err = str(e).lower()
                    if "already exists" in err or "duplicate column" in err:
                        pass # Column exists, safe to ignore
                    else:
                        print(f"CRITICAL: Failed to add column {col}: {e}")
                        raise e # Fail hard so we don't start with broken schema 

            # 1. Add columns to existing tables since CREATE TABLE IF NOT EXISTS won't add them
            safe_add_column("pending_transactions", "latitude", "DECIMAL(10, 8)")
            safe_add_column("pending_transactions", "longitude", "DECIMAL(11, 8)")
            safe_add_column("pending_transactions", "location_name", "VARCHAR")
            safe_add_column("pending_transactions", "created_at", "TIMESTAMP")
            
            # 1b. Add columns to CONFIRMED transactions table (for auto-ingest)
            safe_add_column("transactions", "latitude", "DECIMAL(10, 8)")
            safe_add_column("transactions", "longitude", "DECIMAL(11, 8)")
            safe_add_column("transactions", "location_name", "VARCHAR")

            # 2. Add mobile_devices table
            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS mobile_devices (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                user_id VARCHAR,
                device_name VARCHAR NOT NULL,
                device_id VARCHAR NOT NULL UNIQUE,
                fcm_token VARCHAR,
                is_approved BOOLEAN DEFAULT FALSE,
                is_enabled BOOLEAN DEFAULT TRUE,
                is_ignored BOOLEAN DEFAULT FALSE,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tenant_id) REFERENCES tenants (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            );
            """))
            
            safe_add_column("mobile_devices", "is_enabled", "BOOLEAN DEFAULT TRUE")
            safe_add_column("mobile_devices", "is_ignored", "BOOLEAN DEFAULT FALSE")
            
            # 3. Add unparsed_messages table
            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS unparsed_messages (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                raw_content VARCHAR NOT NULL,
                subject VARCHAR,
                sender VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tenant_id) REFERENCES tenants (id)
            );
            """))
            
            # Explicitly commit the transaction!
            connection.commit()
            print("Auto-migration complete.")
            
    except Exception as e:
        # Re-raise lock errors or critical failures so the app doesn't start in a bad state
        print(f"CRITICAL: Migration failed: {e}")
        raise e
