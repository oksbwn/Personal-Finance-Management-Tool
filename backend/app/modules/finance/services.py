import json
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from backend.app.modules.finance import models, schemas
from datetime import datetime

class FinanceService:
    # --- Accounts ---
    def create_account(db: Session, account: schemas.AccountCreate, tenant_id: str) -> models.Account:
        db_account = models.Account(
            **account.model_dump(),
            tenant_id=tenant_id
        )
        if hasattr(db_account, 'owner_id') and db_account.owner_id:
             db_account.owner_id = str(db_account.owner_id) # Ensure string

        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        return db_account

    def get_accounts(db: Session, tenant_id: str, owner_id: Optional[str] = None) -> List[models.Account]:
        query = db.query(models.Account).filter(models.Account.tenant_id == tenant_id)
        if owner_id:
            query = query.filter((models.Account.owner_id == owner_id) | (models.Account.owner_id == None))
        return query.all()

    def update_account(db: Session, account_id: str, account_update: schemas.AccountUpdate, tenant_id: str) -> Optional[models.Account]:
        db_account = db.query(models.Account).filter(
            models.Account.id == account_id,
            models.Account.tenant_id == tenant_id
        ).first()
        
        if not db_account:
            return None
            
        update_data = account_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_account, key, value)
            
        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        return db_account

    # --- Transactions ---
    def create_transaction(db: Session, transaction: schemas.TransactionCreate, tenant_id: str) -> models.Transaction:
        # Deduplication Check: external_id
        if transaction.external_id:
            existing = db.query(models.Transaction).filter(
                models.Transaction.account_id == str(transaction.account_id),
                models.Transaction.external_id == transaction.external_id,
                models.Transaction.tenant_id == tenant_id
            ).first()
            if existing:
                # Idempotency: Return existing transaction instead of creating duplicate
                return existing

        # Serialize tags if present
        tags_str = json.dumps(transaction.tags) if transaction.tags else None
        
        # --- Auto-Categorization Logic ---
        final_category = transaction.category
        if (not final_category or final_category == "Uncategorized") and transaction.description:
            # Fetch all rules ordered by priority descending
            rules = db.query(models.CategoryRule).order_by(models.CategoryRule.priority.desc()).all()
            
            desc_lower = transaction.description.lower()
            for rule in rules:
                try:
                    keywords = json.loads(rule.keywords)
                    # Check if any keyword matches
                    if any(k.lower() in desc_lower for k in keywords):
                        final_category = rule.category
                        print(f"DEBUG: Rule '{rule.name}' matched! Applied category '{final_category}'")
                        break
                except Exception as e:
                    print(f"Error parsing rule keywords: {e}")
        # ---------------------------------
        
        # Infer Type from Amount
        # Negative amount = DEBIT (Expense)
        # Positive amount = CREDIT (Income)
        txn_type = models.TransactionType.DEBIT if transaction.amount < 0 else models.TransactionType.CREDIT

        db_transaction = models.Transaction(
            account_id=str(transaction.account_id),
            tenant_id=tenant_id,
            amount=transaction.amount,
            date=transaction.date,
            description=transaction.description,
            category=final_category,
            tags=tags_str,
            external_id=transaction.external_id,
            type=txn_type
        )
        
        # Update Account Balance
        # We should ideally fetch and update account balance here
        db_account = db.query(models.Account).filter(models.Account.id == str(transaction.account_id)).first()
        if db_account:
            # Assuming db_account.balance is set
            current_bal = db_account.balance or 0
            db_account.balance = current_bal + transaction.amount
            db.add(db_account)

        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return db_transaction

    def get_transactions(
        db: Session, 
        tenant_id: str, 
        account_id: Optional[str] = None, 
        limit: int = 100
    ) -> List[models.Transaction]:
        query = db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id)
        if account_id:
            query = query.filter(models.Transaction.account_id == account_id)
        return query.order_by(models.Transaction.date.desc()).limit(limit).all()

    def update_transaction(db: Session, txn_id: str, txn_update: schemas.TransactionUpdate, tenant_id: str) -> Optional[models.Transaction]:
        db_txn = db.query(models.Transaction).filter(
            models.Transaction.id == txn_id,
            models.Transaction.tenant_id == tenant_id
        ).first()
        
        if not db_txn:
            return None
            
        update_data = txn_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'tags' and value is not None:
                setattr(db_txn, key, json.dumps(value))
            else:
                setattr(db_txn, key, value)
                
        db.commit()
        db.refresh(db_txn)
        return db_txn

    # --- Metrics ---
    def get_summary_metrics(db: Session, tenant_id: str):
        from datetime import datetime
        
        # Net Worth: Sum of all account balances
        accounts = db.query(models.Account).filter(models.Account.tenant_id == tenant_id).all()
        net_worth = sum(acc.balance or 0 for acc in accounts)
        
        # Monthly Spending: Sum of negative transactions in current month
        # We calculate the magnitude (absolute value) of spending
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        txns = db.query(models.Transaction).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_month,
            models.Transaction.amount < 0 
        ).all()
        
        # Sum is negative (e.g. -500), so we negate it to get positive spending (500)
        monthly_spending = -sum(txn.amount for txn in txns)
        
        return {
            "net_worth": net_worth,
            "monthly_spending": monthly_spending,
            "currency": accounts[0].currency if accounts else "INR"
        }

    # --- Rules ---
    def create_category_rule(db: Session, rule: schemas.CategoryRuleCreate, tenant_id: str) -> models.CategoryRule:
        db_rule = models.CategoryRule(
            **rule.model_dump(),
            tenant_id=tenant_id
        )
        # Serialize keywords list to string
        if isinstance(rule.keywords, list):
             db_rule.keywords = json.dumps(rule.keywords)
             
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        
        # Manually deserialize keywords for Pydantic response
        try:
             db_rule.keywords = json.loads(db_rule.keywords)
        except:
             db_rule.keywords = []
             
        return db_rule

    def get_category_rules(db: Session, tenant_id: str) -> List[models.CategoryRule]:
        rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).order_by(models.CategoryRule.priority.desc()).all()
        # Parse keywords back to list for schema validation? 
        # Actually Pydantic 'from_attributes' might struggle with String -> List[str] auto-conversion if models.py has a String column.
        # We might need a small hack or ensuring the response model handles it.
        for r in rules:
             try:
                 r.keywords = json.loads(r.keywords)
             except:
                 r.keywords = []
        return rules

    def update_category_rule(db: Session, rule_id: str, rule_update: schemas.CategoryRuleUpdate, tenant_id: str) -> Optional[models.CategoryRule]:
        db_rule = db.query(models.CategoryRule).filter(
            models.CategoryRule.id == rule_id,
            models.CategoryRule.tenant_id == tenant_id
        ).first()
        
        if not db_rule:
            return None
            
        update_data = rule_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'keywords' and value is not None:
                setattr(db_rule, key, json.dumps(value))
            else:
                setattr(db_rule, key, value)
                
        db.commit()
        db.refresh(db_rule)
        
        # Deserialize for response
        try:
             db_rule.keywords = json.loads(db_rule.keywords)
        except:
             db_rule.keywords = []
             
        return db_rule

    def delete_category_rule(db: Session, rule_id: str, tenant_id: str) -> bool:
        db_rule = db.query(models.CategoryRule).filter(
            models.CategoryRule.id == rule_id,
            models.CategoryRule.tenant_id == tenant_id
        ).first()
        
        if not db_rule:
            return False
            
        db.delete(db_rule)
        db.commit()
        return True

    def get_rule_suggestions(db: Session, tenant_id: str) -> List[dict]:
        """
        Analyze transaction history to suggest new rules.
        """
        from sqlalchemy import func
        
        # 1. Get existing rules to filter out already covered descriptions?
        # Ideally, we want to find descriptions that are CATEGORIZED but NOT via a rule (manual).
        # But we don't strictly track 'how' it was categorized (manual vs auto).
        # Heuristic: Find commonly occurring descriptions with consistent categories.
        
        # Group by Description + Category
        # DuckDB/SQLAlchemy group by
        results = db.query(
            models.Transaction.description,
            models.Transaction.category,
            func.count(models.Transaction.id).label("count")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.category != "Uncategorized",
            models.Transaction.category != None
        ).group_by(
            models.Transaction.description, 
            models.Transaction.category
        ).having(
            func.count(models.Transaction.id) >= 1 # Suggest even if it happened once? Maybe >= 2 is better signal. Using 1 for now to show potential.
        ).order_by(
            func.count(models.Transaction.id).desc()
        ).limit(10).all()
        
        suggestions = []
        existing_rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).all()
        
        # Flatten existing keywords for basic dedup
        existing_keywords = set()
        for r in existing_rules:
            try:
                kw = json.loads(r.keywords)
                for k in kw: existing_keywords.add(k.lower())
            except: pass

        for row in results:
            desc = row.description
            cat = row.category
            count = row.count
            
            # Simple keyword extraction: Use the whole description or first word? 
            # For "Uber Rides", keyword "Uber" is better.
            # For now, let's suggest the *entire* description as the keyword.
            if desc.lower() in existing_keywords:
                continue
                
            suggestions.append({
                "name": f"Auto-tag {desc}",
                "category": cat,
                "keywords": [desc], # Suggest full description as exact match keyword
                "confidence": count # Use count as proxy for confidence
            })
            
        return suggestions

    # --- Category Management ---
    def get_categories(db: Session, tenant_id: str) -> List[models.Category]:
        cats = db.query(models.Category).filter(models.Category.tenant_id == tenant_id).all()
        if not cats:
            # Seed defaults
            defaults = [
                ("Food & Dining", "🍔"), ("Groceries", "🥦"), ("Transport", "🚌"), 
                ("Shopping", "🛍️"), ("Utilities", "💡"), ("Housing", "🏠"),
                ("Healthcare", "🏥"), ("Entertainment", "🎬"), ("Salary", "💰"),
                ("Investment", "📈"), ("Education", "🎓"), ("Other", "📦")
            ]
            new_cats = []
            for name, icon in defaults:
                c = models.Category(tenant_id=tenant_id, name=name, icon=icon)
                db.add(c)
                new_cats.append(c)
            db.commit()
            return new_cats
        return cats

    def create_category(db: Session, category: schemas.CategoryCreate, tenant_id: str) -> models.Category:
        db_cat = models.Category(
            **category.model_dump(),
            tenant_id=tenant_id
        )
        db.add(db_cat)
        db.commit()
        db.refresh(db_cat)
        return db_cat

    def update_category(db: Session, category_id: str, update: schemas.CategoryUpdate, tenant_id: str) -> Optional[models.Category]:
        db_cat = db.query(models.Category).filter(models.Category.id == category_id, models.Category.tenant_id == tenant_id).first()
        if not db_cat: return None
        
        data = update.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(db_cat, k, v)
            
        db.commit()
        db.refresh(db_cat)
        return db_cat

    def delete_category(db: Session, category_id: str, tenant_id: str) -> bool:
        db_cat = db.query(models.Category).filter(models.Category.id == category_id, models.Category.tenant_id == tenant_id).first()
        if not db_cat: return False
        db.delete(db_cat)
        db.commit()
        return True

    # --- Budgets ---
    def get_budgets(db: Session, tenant_id: str) -> List[dict]:
        """
        Get all budgets and calculate progress based on current month's spending.
        """
        from datetime import datetime
        budgets = db.query(models.Budget).filter(models.Budget.tenant_id == tenant_id).all()
        
        # Calculate spending for current month
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        # Helper to get spending for a category
        # Optimized: Aggregate all spending for current month first
        from sqlalchemy import func
        spending_rows = db.query(
            models.Transaction.category, 
            func.sum(models.Transaction.amount).label("sum")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.date >= start_of_month,
            models.Transaction.amount < 0 # Only expenses
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

    def delete_budget(db: Session, budget_id: str, tenant_id: str) -> bool:
        b = db.query(models.Budget).filter(models.Budget.id == budget_id, models.Budget.tenant_id == tenant_id).first()
        if not b: return False
        db.delete(b)
        db.commit()
        return True
