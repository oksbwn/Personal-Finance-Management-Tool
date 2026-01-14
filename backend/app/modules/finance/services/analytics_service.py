from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.modules.finance import models
from backend.app.modules.finance.services.transaction_service import TransactionService

class AnalyticsService:
    @staticmethod
    def get_summary_metrics(db: Session, tenant_id: str, user_role: str = "ADULT"):
        
        # 1. Accounts & Net Worth
        accounts_query = db.query(models.Account).filter(models.Account.tenant_id == tenant_id)
        if user_role == "CHILD":
            accounts_query = accounts_query.filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))
        
        accounts = accounts_query.all()
        
        # Categorize Balances
        breakdown = {
            "net_worth": 0,
            "bank_balance": 0,
            "cash_balance": 0,
            "credit_debt": 0,
            "investment_value": 0,
            "total_credit_limit": 0,
            "available_credit": 0
        }
        
        for acc in accounts:
            bal = float(acc.balance or 0)
            if acc.type == 'CREDIT_CARD':
                breakdown["credit_debt"] += bal
                breakdown["net_worth"] -= bal
                
                limit = float(acc.credit_limit or 0)
                breakdown["total_credit_limit"] += limit
                breakdown["available_credit"] += (limit - bal)
            
            elif acc.type == 'INVESTMENT':
                breakdown["investment_value"] += bal
                breakdown["net_worth"] += bal
            
            elif acc.type == 'LOAN':
                breakdown["net_worth"] -= bal
                
            else:
                # Bank, Wallet, etc.
                breakdown["net_worth"] += bal
                if acc.type == 'BANK': breakdown["bank_balance"] += bal
                elif acc.type == 'WALLET': breakdown["cash_balance"] += bal

        # 2. Monthly Spending
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        txns_query = db.query(models.Transaction).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_month,
            models.Transaction.amount < 0,
            models.Transaction.is_transfer == False
        )
        if user_role == "CHILD":
             txns_query = txns_query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                                    .filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))
        
        monthly_spending = abs(sum(txn.amount for txn in txns_query.all()))
        
        # 3. Overall Budget Health
        all_budgets = db.query(models.Budget).filter(models.Budget.tenant_id == tenant_id).all()
        overall = next((b for b in all_budgets if b.category == 'OVERALL'), None)
        total_budget_limit = float(overall.amount_limit) if overall else 0
        if not overall and all_budgets:
            total_budget_limit = sum(float(b.amount_limit) for b in all_budgets)
            
        budget_health = {
            "limit": total_budget_limit,
            "spent": float(monthly_spending),
            "percentage": (float(monthly_spending) / total_budget_limit * 100) if total_budget_limit > 0 else 0
        }
        
        # 4. Recent Transactions
        # Avoid circular import at top level if possible, or Import inside method
        recent_txns = TransactionService.get_transactions(db, tenant_id, limit=5, user_role=user_role)
        
        return {
            "breakdown": breakdown,
            "monthly_spending": monthly_spending,
            "budget_health": budget_health,
            "recent_transactions": recent_txns,
            "currency": accounts[0].currency if accounts else "INR"
        }
