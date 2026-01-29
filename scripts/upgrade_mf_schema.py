
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import SessionLocal, engine 

def upgrade_db():
    db = SessionLocal()
    try:
        print("Checking for transaction_hash column...")
        try:
            db.execute(text("SELECT transaction_hash FROM mutual_fund_orders LIMIT 1"))
            print("Column exists.")
        except Exception:
            print("Column missing. Adding transaction_hash...")
            db.rollback()
            db.execute(text("ALTER TABLE mutual_fund_orders ADD COLUMN transaction_hash VARCHAR"))
            db.commit()
            print("Column added successfully.")
        
        print("Checking for benchmark_value column in cache...")
        try:
            db.execute(text("SELECT benchmark_value FROM portfolio_timeline_cache LIMIT 1"))
            print("Benchmark Column exists.")
        except Exception:
            print("Benchmark Column missing. Adding...")
            db.execute(text("ALTER TABLE portfolio_timeline_cache ADD COLUMN benchmark_value DOUBLE"))
            db.commit()
            print("Benchmark Column added.")
            
        
    except Exception as e:
        print(f"Error during upgrade: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    upgrade_db()
