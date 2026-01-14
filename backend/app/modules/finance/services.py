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
        data = account.model_dump()
        if not data.get('tenant_id'):
            data['tenant_id'] = tenant_id
            
        db_account = models.Account(**data)
        if hasattr(db_account, 'owner_id') and db_account.owner_id:
             db_account.owner_id = str(db_account.owner_id) # Ensure string

        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        return db_account

    def get_accounts(db: Session, tenant_id: str, owner_id: Optional[str] = None, user_role: str = "ADULT") -> List[models.Account]:
        query = db.query(models.Account).filter(models.Account.tenant_id == tenant_id)
        if owner_id:
            query = query.filter((models.Account.owner_id == owner_id) | (models.Account.owner_id == None))
        
        # Role-based restriction: Kids can't see Investments or Credit Cards
        if user_role == "CHILD":
            query = query.filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))
            
        return query.all()

    def update_account(db: Session, account_id: str, account_update: schemas.AccountUpdate, tenant_id: str) -> Optional[models.Account]:
        db_account = db.query(models.Account).filter(
            models.Account.id == account_id,
            models.Account.tenant_id == tenant_id
        ).first()
        
        if not db_account:
            return None
            
        update_data = account_update.model_dump(exclude_unset=True)
        if not update_data:
            return db_account
        
        # Apply updates
        for key, value in update_data.items():
            if key in ['tenant_id', 'owner_id'] and value:
                value = str(value)
            setattr(db_account, key, value)
        
        try:
            db.commit()
            db.refresh(db_account)
            return db_account
        except Exception as e:
            db.rollback()
            # DuckDB limitation: Cannot update accounts that have transactions
            # This is a known DuckDB foreign key constraint issue
            print(f"Account update error (likely DuckDB FK limitation): {e}")
            raise

    def delete_account(db: Session, account_id: str, tenant_id: str) -> bool:
        db_account = db.query(models.Account).filter(
            models.Account.id == account_id,
            models.Account.tenant_id == tenant_id
        ).first()
        
        if not db_account:
            return False
            
        db.delete(db_account)
        db.commit()
        return True

    # --- Transactions ---
    def create_transaction(db: Session, transaction: schemas.TransactionCreate, tenant_id: str) -> models.Transaction:
        # Deduplication Check: external_id
        if transaction.external_id:
            # Universal Deduplication: Check across ALL accounts for this tenant
            existing = db.query(models.Transaction).filter(
                models.Transaction.tenant_id == tenant_id,
                models.Transaction.external_id == transaction.external_id
            ).first()
            
            if existing:
                # Idempotency: Return existing transaction
                return existing

        # Serialize tags if present
        tags_str = json.dumps(transaction.tags) if transaction.tags else None
        
        # --- Auto-Categorization Logic ---
        final_category = transaction.category
        if (not final_category or final_category == "Uncategorized") and (transaction.description or transaction.recipient):
            # Fetch all rules ordered by priority descending
            rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).order_by(models.CategoryRule.priority.desc()).all()
            
            desc_lower = (transaction.description or "").lower()
            recipient_lower = (transaction.recipient or "").lower()
            
            for rule in rules:
                try:
                    keywords = json.loads(rule.keywords)
                    # Check if any keyword matches description OR recipient
                    if any(k.lower() in desc_lower or k.lower() in recipient_lower for k in keywords):
                        final_category = rule.category
                        print(f"✓ Auto-categorized: Rule '{rule.name}' matched! Applied category '{final_category}'")
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
            recipient=transaction.recipient,
            category=final_category,
            tags=tags_str,
            external_id=transaction.external_id,
            type=txn_type,
            is_transfer=transaction.is_transfer,
            linked_transaction_id=getattr(transaction, 'linked_transaction_id', None),
            source=transaction.source if hasattr(transaction, 'source') else "MANUAL"
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
        skip: int = 0,
        limit: int = 50,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_role: str = "ADULT"
    ) -> List[models.Transaction]:
        query = db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id)
        
        # Role-based restriction for Kids
        if user_role == "CHILD":
            query = query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                         .filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))

        if account_id:
            query = query.filter(models.Transaction.account_id == account_id)
        if start_date:
            query = query.filter(models.Transaction.date >= start_date)
        if end_date:
            query = query.filter(models.Transaction.date <= end_date)
            
        return query.order_by(models.Transaction.date.desc()).offset(skip).limit(limit).all()

    def count_transactions(
        db: Session, 
        tenant_id: str, 
        account_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_role: str = "ADULT"
    ) -> int:
        query = db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id)

        # Role-based restriction for Kids
        if user_role == "CHILD":
            query = query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                         .filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))

        if account_id:
            query = query.filter(models.Transaction.account_id == account_id)
        if start_date:
            query = query.filter(models.Transaction.date >= start_date)
        if end_date:
            query = query.filter(models.Transaction.date <= end_date)
            
        return query.count()

    def bulk_delete_transactions(db: Session, transaction_ids: List[str], tenant_id: str) -> int:
        if not transaction_ids: return 0
        try:
            # Use synchronize_session=False for bulk delete performance
            query = db.query(models.Transaction).filter(
                models.Transaction.id.in_(transaction_ids),
                models.Transaction.tenant_id == tenant_id
            )
            count = query.delete(synchronize_session=False)
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            raise e

    def update_transaction(db: Session, txn_id: str, txn_update: schemas.TransactionUpdate, tenant_id: str) -> Optional[models.Transaction]:
        db_txn = db.query(models.Transaction).filter(
            models.Transaction.id == txn_id,
            models.Transaction.tenant_id == tenant_id
        ).first()
        
        if not db_txn:
            return None
            
        update_data = txn_update.model_dump(exclude_unset=True)
        
        # Check if transfer status is changing
        is_transfer_update = update_data.get('is_transfer')
        to_account_id = update_data.get('to_account_id')
        
        # Case A: Converting to Transfer (or updating transfer details)
        if is_transfer_update is True:
            if not to_account_id and not db_txn.linked_transaction_id:
                # If conversion, we need a destination
                 # If just updating other fields of an existing transfer, to_account_id might be missing from update
                 pass 

            if to_account_id:
                # 1. Unlink old if exists (e.g. changing destination)
                if db_txn.linked_transaction_id:
                     old_linked = db.query(models.Transaction).filter(models.Transaction.id == db_txn.linked_transaction_id).first()
                     if old_linked: db.delete(old_linked)
                
                # 2. Create new linked transaction
                from backend.app.modules.finance.models import TransactionType
                import uuid
                
                target_txn = models.Transaction(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    account_id=to_account_id,
                    amount=-db_txn.amount if 'amount' not in update_data else -update_data['amount'],
                    date=db_txn.date if 'date' not in update_data else update_data['date'],
                    description=f"Transfer from {db_txn.account_id} (Linked)",
                    recipient=db_txn.recipient,
                    category="Transfer",
                    type=TransactionType.CREDIT if (db_txn.amount < 0) else TransactionType.DEBIT,
                    is_transfer=True,
                    source=db_txn.source,
                    linked_transaction_id=db_txn.id
                )
                db.add(target_txn)
                db_txn.linked_transaction_id = target_txn.id
                db_txn.category = "Transfer" # Force category
                update_data['category'] = "Transfer"

        # Case B: Disabling Transfer
        elif is_transfer_update is False:
            if db_txn.linked_transaction_id:
                linked = db.query(models.Transaction).filter(models.Transaction.id == db_txn.linked_transaction_id).first()
                if linked: db.delete(linked)
                db_txn.linked_transaction_id = None
        
        # Apply standard updates
        for key, value in update_data.items():
            if key in ['is_transfer', 'to_account_id']: continue # Handled above
            if key == 'tags' and value is not None:
                setattr(db_txn, key, json.dumps(value))
            else:
                setattr(db_txn, key, value)
                
        db.commit()
        db.refresh(db_txn)
        return db_txn

    @staticmethod
    def get_suggested_category(db: Session, tenant_id: str, description: Optional[str], recipient: Optional[str]) -> str:
        if not description and not recipient:
            return "Uncategorized"
            
        rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).order_by(models.CategoryRule.priority.desc()).all()
        
        desc_lower = (description or "").lower()
        recipient_lower = (recipient or "").lower()
        
        for rule in rules:
            try:
                keywords = json.loads(rule.keywords)
                if any(k.lower() in desc_lower or k.lower() in recipient_lower for k in keywords):
                    return rule.category
            except:
                continue
        return "Uncategorized"

    # --- Triage Functions ---
    @staticmethod
    def get_pending_transactions(db: Session, tenant_id: str):
        from backend.app.modules.ingestion import models as ingestion_models
        return db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).order_by(ingestion_models.PendingTransaction.created_at.desc()).all()

    @staticmethod
    def approve_pending_transaction(
        db: Session, 
        pending_id: str, 
        tenant_id: str, 
        category_override: Optional[str] = None,
        is_transfer_override: bool = False,
        to_account_id_override: Optional[str] = None,
        create_rule: bool = False
    ):
        from backend.app.modules.ingestion import models as ingestion_models
        pending = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.id == pending_id,
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).first()
        if not pending: return None
        
        # Apply manual overrides if provided
        final_is_transfer = is_transfer_override or pending.is_transfer
        final_to_account_id = to_account_id_override or pending.to_account_id
        final_category = category_override or pending.category or "Uncategorized"
        
        # 1. Create Rule if requested (Caching manual decision)
        if create_rule and pending.description:
            rule_create = schemas.CategoryRuleCreate(
                name=f"Rule for {pending.description[:20]}...",
                category=final_category,
                keywords=[pending.description],
                is_transfer=final_is_transfer,
                to_account_id=final_to_account_id,
                priority=10
            )
            FinanceService.create_category_rule(db, rule_create, tenant_id)

        # Convert to real transaction
        txn_create = schemas.TransactionCreate(
            account_id=pending.account_id,
            amount=pending.amount,
            date=pending.date,
            description=pending.description,
            recipient=pending.recipient,
            category=final_category,
            external_id=pending.external_id,
            source=pending.source,
            is_transfer=final_is_transfer,
            to_account_id=final_to_account_id,
            tags=[]
        )
        
        # If it's a transfer, let TransferService handle it
        if txn_create.is_transfer and txn_create.to_account_id:
            from backend.app.modules.finance.transfer_service import TransferService
            # We need to temporarily update pending object fields so TransferService uses correct data if overridden
            pending.is_transfer = final_is_transfer
            pending.to_account_id = final_to_account_id
            real_txn = TransferService.approve_transfer(db, pending, tenant_id)
        else:
            # We reuse create_transaction
            real_txn = FinanceService.create_transaction(db, txn_create, tenant_id)
        
        # Update Account Balance/Credit Limit if provided
        if pending.balance is not None or pending.credit_limit is not None:
            account = db.query(models.Account).filter(models.Account.id == pending.account_id).first()
            if account:
                if pending.balance is not None:
                    account.balance = pending.balance
                if pending.credit_limit is not None:
                    account.credit_limit = pending.credit_limit

        # Delete pending
        db.delete(pending)
        db.commit()
        return real_txn

    @staticmethod
    def reject_pending_transaction(db: Session, pending_id: str, tenant_id: str):
        from backend.app.modules.ingestion import models as ingestion_models
        pending = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.id == pending_id,
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).first()
        if not pending: return False
        db.delete(pending)
        db.commit()
        return True

    # --- Metrics ---
    def get_summary_metrics(db: Session, tenant_id: str, user_role: str = "ADULT"):
        from datetime import datetime
        
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
                breakdown["credit_debt"] += bal # Debt is stored as positive utilization usually?
                                                # Wait, conventions: 
                                                # If we treat Expense as Debit (-ve), then Credit Card balance could be:
                                                # -ve (Owed to bank) OR +ve (Bank owes us)
                                                # Usually in apps: +ve Balance on Credit Card = Debt.
                                                # Let's assume +ve balance = Used Amount.
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
        
        # 3. Overall Budget Health (Reuse logic roughly)
        # We need total budget limit vs spent
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
        recent_txns = FinanceService.get_transactions(db, tenant_id, limit=5, user_role=user_role)
        
        return {
            "breakdown": breakdown,
            "monthly_spending": monthly_spending,
            "budget_health": budget_health,
            "recent_transactions": recent_txns,
            "currency": accounts[0].currency if accounts else "INR"
        }

    # --- Rules ---
    def create_category_rule(db: Session, rule: schemas.CategoryRuleCreate, tenant_id: str) -> models.CategoryRule:
        data = rule.model_dump()
        if isinstance(data.get('keywords'), list):
            data['keywords'] = json.dumps(data['keywords'])
            
        db_rule = models.CategoryRule(
            **data,
            tenant_id=tenant_id
        )
             
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

    # --- Smart Categorization ---
    def batch_update_category_and_create_rule(
        db: Session, 
        txn_id: str, 
        category: str, 
        tenant_id: str,
        create_rule: bool = False,
        apply_to_similar: bool = False
    ) -> dict:
        """
        1. Updates a specific transaction's category.
        2. Optionally creates a persistent CategoryRule.
        3. Optionally updates all other similar Uncategorized transactions.
        """
        # 1. Update the original transaction
        db_txn = db.query(models.Transaction).filter(
            models.Transaction.id == txn_id,
            models.Transaction.tenant_id == tenant_id
        ).first()
        
        if not db_txn:
            return {"success": False, "message": "Transaction not found"}
            
        old_category = db_txn.category
        db_txn.category = category
        db.add(db_txn)
        
        affected_count = 1
        rule_created = False
        
        # Determine the "Pattern" to match (Priority: Recipient > Description)
        pattern = db_txn.recipient or db_txn.description
        if not pattern:
            db.commit()
            return {"success": True, "affected": infected_count, "rule_created": False}

        # 2. Create Persistent Rule if requested
        if create_rule:
            # Check if a rule already exists for this pattern
            existing_rule = db.query(models.CategoryRule).filter(
                models.CategoryRule.tenant_id == tenant_id,
                models.CategoryRule.name == f"Auto: {pattern}"
            ).first()
            
            if not existing_rule:
                new_rule = models.CategoryRule(
                    tenant_id=tenant_id,
                    name=f"Auto: {pattern}",
                    category=category,
                    keywords=json.dumps([pattern]),
                    priority=1
                )
                db.add(new_rule)
                rule_created = True

        # 3. Apply to Similar Uncategorized Transactions
        if apply_to_similar:
            # Find all transactions with the same recipient or description that are STILL Uncategorized
            query = db.query(models.Transaction).filter(
                models.Transaction.tenant_id == tenant_id,
                models.Transaction.id != txn_id, # Don't re-update self
                (models.Transaction.category == "Uncategorized") | (models.Transaction.category == None)
            )
            
            if db_txn.recipient:
                query = query.filter(models.Transaction.recipient == db_txn.recipient)
            else:
                query = query.filter(models.Transaction.description == db_txn.description)
                
            similar_txns = query.all()
            for st in similar_txns:
                st.category = category
                db.add(st)
                affected_count += 1

        db.commit()
        return {
            "success": True, 
            "affected": affected_count, 
            "rule_created": rule_created,
            "pattern": pattern
        }
