
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import SessionLocal, engine 

def cleanup_mutual_funds():
    db = SessionLocal()
    try:
        print("Cleaning up Mutual Fund data...")
        
        # Delete from child tables first if there are foreign keys, though here relationships are loose
        # or managed by app logic.
        
        # Delete Orders
        print("Deleting existing Mutual Fund Orders...")
        db.execute(text("DELETE FROM mutual_fund_orders"))
        
        # Delete Holdings
        print("Deleting existing Mutual Fund Holdings...")
        db.execute(text("DELETE FROM mutual_fund_holdings"))
        
        # Delete Portfolio Timeline Cache
        print("Deleting Portfolio Timeline Cache...")
        db.execute(text("DELETE FROM portfolio_timeline_cache"))
        
        db.commit()
        print("Successfully cleaned up all Mutual Fund user data.")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_mutual_funds()
