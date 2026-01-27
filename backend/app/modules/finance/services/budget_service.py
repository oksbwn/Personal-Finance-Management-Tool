from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from backend.app.modules.finance import models, schemas

class BudgetService:
    @staticmethod
    def get_budgets(db: Session, tenant_id: str, year: int = None, month: int = None) -> List[dict]:
        """
        Get all budgets and calculate progress based on target month's spending.
        Includes all defined categories so we can see activity even without a limit.
        """
        budgets = db.query(models.Budget).filter(models.Budget.tenant_id == tenant_id).all()
        categories = db.query(models.Category).filter(models.Category.tenant_id == tenant_id).all()
        
        # Determine period
        now = datetime.utcnow()
        if not year: year = now.year
        if not month: month = now.month
        
        start_of_period = datetime(year, month, 1)
        if month == 12:
            end_of_period = datetime(year + 1, 1, 1)
        else:
            end_of_period = datetime(year, month + 1, 1)
        
        # Helper to get spending for categories
        spending_rows = db.query(
            models.Transaction.category, 
            func.sum(models.Transaction.amount).label("sum")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_period,
            models.Transaction.date < end_of_period,
            models.Transaction.is_transfer == False,
            models.Transaction.exclude_from_reports == False
        ).group_by(models.Transaction.category).all()
        
        spending_map = {}
        for row in spending_rows:
            name = row.category or 'Uncategorized'
            spending_map[name] = spending_map.get(name, Decimal(0)) + (row.sum or Decimal(0))
        
        # 2b. Helper to get excluded spending per category (for per-category display)
        excluded_rows = db.query(
            models.Transaction.category,
            func.sum(models.Transaction.amount).label("sum")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_period,
            models.Transaction.date < end_of_period,
            or_(models.Transaction.exclude_from_reports == True, models.Transaction.is_transfer == True)
        ).group_by(models.Transaction.category).all()
        
        excluded_map = { (row.category or 'Uncategorized'): row.sum for row in excluded_rows }
        
        # Calculate total volume by polarity (not grouped) to catch transfers
        excluded_spending = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_period,
            models.Transaction.date < end_of_period,
            or_(models.Transaction.exclude_from_reports == True, models.Transaction.is_transfer == True),
            models.Transaction.amount < 0
        ).scalar() or Decimal(0)
        
        excluded_income = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_period,
            models.Transaction.date < end_of_period,
            or_(models.Transaction.exclude_from_reports == True, models.Transaction.is_transfer == True),
            models.Transaction.amount > 0
        ).scalar() or Decimal(0)

        excluded_spending = abs(excluded_spending)
        
        # 2c.
        
        budget_map = {b.category: b for b in budgets}
        category_map = {c.name: c for c in categories}
        
        # Also track overall
        total_expense = sum(abs(v) for v in spending_map.values() if v < 0)
        total_income = sum(v for v in spending_map.values() if v > 0)
        
        results = []
        
        # 1. Start with OVERALL if it exists
        overall_b = budget_map.get('OVERALL')
        if overall_b or total_expense > 0 or total_income > 0 or excluded_spending != 0 or excluded_income != 0:
            limit = overall_b.amount_limit if overall_b else None
            spent = total_expense
            results.append({
                "category": "OVERALL",
                "amount_limit": limit,
                "spent": spent,
                "income": total_income,
                "total_excluded": excluded_spending,
                "excluded_income": excluded_income,
                "remaining": limit - spent if limit else None,
                "percentage": (float(spent) / float(limit)) * 100 if limit and limit > 0 else 0,
                "id": overall_b.id if overall_b else None,
                "budget_id": overall_b.id if overall_b else None,
                "tenant_id": tenant_id,
                "period": "MONTHLY",
                "updated_at": overall_b.updated_at if overall_b else None,
                "type": "expense",
                "icon": "🏁",
                "color": "#10B981"
            })

        # 2. Iterate through all categories to show progress
        # We want to include categories that have a budget OR have spending (regular or excluded)
        active_cat_names = set(category_map.keys()) | set(spending_map.keys()) | set(budget_map.keys()) | set(excluded_map.keys())
        active_cat_names.discard('OVERALL')
        
        for name in sorted(list(active_cat_names)):
            b = budget_map.get(name)
            c = category_map.get(name)
            value = spending_map.get(name, Decimal(0))
            ex_value = excluded_map.get(name, Decimal(0))
            
            spent = abs(value) if value < 0 else Decimal(0)
            income = value if value > 0 else Decimal(0)
            
            limit = b.amount_limit if b else None
            remaining = limit - spent if limit else None
            percentage = (float(spent) / float(limit)) * 100 if limit and limit > 0 else 0
            
            results.append({
                "category": name,
                "amount_limit": limit,
                "spent": spent,
                "income": income,
                "excluded": abs(ex_value),
                "remaining": remaining,
                "percentage": percentage,
                "id": b.id if b else None,
                "budget_id": b.id if b else None,
                "tenant_id": tenant_id,
                "period": "MONTHLY",
                "updated_at": b.updated_at if b else None,
                "type": c.type if c else "expense",
                "icon": c.icon if c else "🏷️",
                "color": c.color if c else "#3B82F6"
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

    @staticmethod
    def get_ai_insights(db: Session, tenant_id: str, year: int = None, month: int = None) -> List[dict]:
        """
        Gathers financial data and generates AI-driven insights/tips.
        """
        data = BudgetService.get_budgets(db, tenant_id, year, month)
        
        # Try Gemini integration first
        try:
            from backend.app.modules.ingestion.ai_service import AIService
            ai_insights = AIService.generate_structured_insights(db, tenant_id, {"budgets": data})
            if ai_insights:
                return ai_insights
        except Exception:
            pass

        # Fallback to hardcoded rules if AI is disabled or fails
        if not data:
            return [{
                "id": "intro",
                "type": "info",
                "title": "Welcome to AI Intelligence",
                "content": "Start adding transactions to get personalized financial insights.",
                "icon": "✨"
            }]

        insights = []
        overall = next((b for b in data if b["category"] == "OVERALL"), None)
        categories = [b for b in data if b["category"] != "OVERALL"]

        # 1. Overall Health
        if overall and overall["amount_limit"]:
            if overall["percentage"] > 100:
                insights.append({
                    "id": "overall_over",
                    "type": "danger",
                    "title": "Action Required: Over Budget",
                    "content": f"You are {overall['percentage']-100:.1f}% over your total limit. Consider cutting non-essentials.",
                    "icon": "🚨"
                })
            elif overall["percentage"] > 80:
                insights.append({
                    "id": "overall_warn",
                    "type": "warning",
                    "title": "Caution: Budget Ceiling",
                    "content": f"You've used {overall['percentage']:.1f}% of your budget. Slow down spending for the rest of the month.",
                    "icon": "⚠️"
                })
            elif overall["percentage"] > 0:
                insights.append({
                    "id": "overall_good",
                    "type": "success",
                    "title": "Healthy Trajectory",
                    "content": "Your overall spending is well within limits. Good job maintaining a buffer!",
                    "icon": "💎"
                })

        # 2. Specific Category Pain Points
        overspent_cats = [c for c in categories if c["amount_limit"] and c["percentage"] > 100]
        if overspent_cats:
            top_offender = max(overspent_cats, key=lambda x: x["spent"])
            insights.append({
                "id": "cat_over",
                "type": "danger",
                "title": f"Drain in {top_offender['category']}",
                "content": f"Spending in {top_offender['category']} is uncontrolled. Try setting a stricter limit next month.",
                "icon": "💸"
            })

        # 3. High Income Performance
        top_income = [c for c in categories if c["income"] > 0]
        if top_income:
            best_income = max(top_income, key=lambda x: x["income"])
            insights.append({
                "id": "income_boost",
                "type": "success",
                "title": "Positive Inflow",
                "content": f"The {best_income['category']} category contributed significantly to your cash flow this month.",
                "icon": "📈"
            })

        # 4. Seasonal/General Tip (Fallback)
        if not insights:
            insights.append({
                "id": "general_tip",
                "type": "info",
                "title": "Pro Tip: Emergency Fund",
                "content": "Aim to save at least 20% of your net income if you haven't started an emergency fund yet.",
                "icon": "🛡️"
            })

        return insights[:3] # Keep it snappy
