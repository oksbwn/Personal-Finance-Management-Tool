from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.modules.finance import models, schemas

class BudgetService:
    @staticmethod
    def get_budgets(db: Session, tenant_id: str) -> List[dict]:
        """
        Get all budgets and calculate progress based on current month's spending.
        """
        budgets = db.query(models.Budget).filter(models.Budget.tenant_id == tenant_id).all()
        
        # Calculate spending for current month
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        # Helper to get spending for a category
        # Optimized: Aggregate all spending for current month first
        spending_rows = db.query(
            models.Transaction.category, 
            func.sum(models.Transaction.amount).label("sum")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_month,
            models.Transaction.amount < 0, # Only expenses
            models.Transaction.is_transfer == False
        ).group_by(models.Transaction.category).all()
        
        spending_map = {row.category: abs(row.sum) for row in spending_rows if row.category}
        total_monthly_spending = sum(spending_map.values())
        
        results = []
        for b in budgets:
            if b.category == 'OVERALL':
                spent = total_monthly_spending
            else:
                spent = spending_map.get(b.category, Decimal(0))
            # Handle decimals for percentage
            amount_limit = b.amount_limit
            remaining = amount_limit - spent
            percentage = (float(spent) / float(amount_limit)) * 100 if amount_limit > 0 else 0
            
            results.append({
                "id": b.id,
                "tenant_id": b.tenant_id,
                "category": b.category,
                "amount_limit": b.amount_limit,
                "period": b.period,
                "updated_at": b.updated_at,
                "spent": spent,
                "remaining": remaining,
                "percentage": percentage
            })
            
        return results

    @staticmethod
    def set_budget(db: Session, budget: schemas.BudgetCreate, tenant_id: str) -> models.Budget:
        # Upsert: Check if budget exists for category
        existing = db.query(models.Budget).filter(
            models.Budget.tenant_id == tenant_id,
            models.Budget.category == budget.category
        ).first()
        
        if existing:
            existing.amount_limit = budget.amount_limit
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_budget = models.Budget(
                tenant_id=tenant_id,
                **budget.model_dump()
            )
            db.add(new_budget)
            db.commit()
            db.refresh(new_budget)
            return new_budget

    @staticmethod
    def delete_budget(db: Session, budget_id: str, tenant_id: str) -> bool:
        b = db.query(models.Budget).filter(models.Budget.id == budget_id, models.Budget.tenant_id == tenant_id).first()
        if not b: return False
        db.delete(b)
        db.commit()
        return True
