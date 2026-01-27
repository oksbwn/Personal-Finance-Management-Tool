from typing import List, Optional
from datetime import datetime
import json
import uuid
from sqlalchemy.orm import Session
from backend.app.modules.finance import models, schemas
from backend.app.modules.finance.models import TransactionType
from backend.app.modules.finance.services.category_service import CategoryService
from backend.app.modules.finance.services.transfer_service import TransferService
from backend.app.modules.ingestion import models as ingestion_models

class TransactionService:
    @staticmethod
    def create_transaction(db: Session, transaction: schemas.TransactionCreate, tenant_id: str) -> models.Transaction:
        # Deduplication Check: external_id
        if transaction.external_id:
            existing = db.query(models.Transaction).filter(
                models.Transaction.tenant_id == tenant_id,
                models.Transaction.external_id == transaction.external_id
            ).first()
            
            if existing:
                return existing

        # Serialize tags if present
        tags_str = json.dumps(transaction.tags) if transaction.tags else None
        
        # --- Auto-Categorization Logic ---
        final_category = transaction.category
        final_exclude = transaction.exclude_from_reports or transaction.is_transfer
        
        if (not final_category or final_category == "Uncategorized") and (transaction.description or transaction.recipient):
            rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).order_by(models.CategoryRule.priority.desc()).all()
            
            desc_lower = (transaction.description or "").lower()
            recipient_lower = (transaction.recipient or "").lower()
            
            for rule in rules:
                try:
                    keywords = json.loads(rule.keywords)
                    if any(k.lower() in desc_lower or k.lower() in recipient_lower for k in keywords):
                        final_category = rule.category
                        if rule.exclude_from_reports:
                            final_exclude = True
                        break
                except Exception as e:
                    pass
        # ---------------------------------
        
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
            external_id=transaction.external_id if transaction.external_id else str(uuid.uuid4()), # Ensure external_id or UUID? Model might allow null, but safer to have ID
            type=txn_type,
            is_transfer=transaction.is_transfer,
            linked_transaction_id=getattr(transaction, 'linked_transaction_id', None),
            source=transaction.source if hasattr(transaction, 'source') else "MANUAL",
            content_hash=getattr(transaction, 'content_hash', None),
            exclude_from_reports=final_exclude
        )
        
        # Update Account Balance
        db_account = db.query(models.Account).filter(models.Account.id == str(transaction.account_id)).first()
        if db_account:
            current_bal = db_account.balance or 0
            db_account.balance = current_bal + transaction.amount
            db.add(db_account)

        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return db_transaction

    @staticmethod
    def get_transactions(
        db: Session, 
        tenant_id: str, 
        account_id: Optional[str] = None, 
        skip: int = 0,
        limit: int = 50,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        category: Optional[str] = None,
        user_role: str = "ADULT",
        user_id: Optional[str] = None
    ) -> List[models.Transaction]:
        query = db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id)
        
        if user_role == "CHILD":
            query = query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                         .filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))

        if account_id:
            query = query.filter(models.Transaction.account_id == account_id)
        if start_date:
            query = query.filter(models.Transaction.date >= start_date)
        if end_date:
            query = query.filter(models.Transaction.date <= end_date)
        
        if search:
            search_pattern = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(
                models.Transaction.description.ilike(search_pattern),
                models.Transaction.recipient.ilike(search_pattern)
            ))
            
        if category:
            query = query.filter(models.Transaction.category == category)

        if user_id:
            # Filter by account ownership: show user's accounts OR shared accounts
            from sqlalchemy import or_
            query = query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                         .filter(or_(models.Account.owner_id == user_id, models.Account.owner_id == None))
            
        return query.order_by(models.Transaction.date.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def count_transactions(
        db: Session, 
        tenant_id: str, 
        account_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        category: Optional[str] = None,
        user_role: str = "ADULT"
    ) -> int:
        query = db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id)

        if user_role == "CHILD":
            query = query.join(models.Account, models.Transaction.account_id == models.Account.id)\
                         .filter(models.Account.type.notin_(["INVESTMENT", "CREDIT"]))

        if account_id:
            query = query.filter(models.Transaction.account_id == account_id)
        if start_date:
            query = query.filter(models.Transaction.date >= start_date)
        if end_date:
            query = query.filter(models.Transaction.date <= end_date)
            
        if search:
            search_pattern = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(
                models.Transaction.description.ilike(search_pattern),
                models.Transaction.recipient.ilike(search_pattern)
            ))
            
        if category:
            query = query.filter(models.Transaction.category == category)
            
        return query.count()

    @staticmethod
    def bulk_delete_transactions(db: Session, transaction_ids: List[str], tenant_id: str) -> int:
        if not transaction_ids: return 0
        try:
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

    @staticmethod
    def update_transaction(db: Session, txn_id: str, txn_update: schemas.TransactionUpdate, tenant_id: str) -> Optional[models.Transaction]:
        db_txn = db.query(models.Transaction).filter(
            models.Transaction.id == txn_id,
            models.Transaction.tenant_id == tenant_id
        ).first()
        
        if not db_txn:
            return None
            
        update_data = txn_update.model_dump(exclude_unset=True)
        
        is_transfer_update = update_data.get('is_transfer')
        to_account_id = update_data.get('to_account_id')
        
        if is_transfer_update is True:
            db_txn.is_transfer = True
            db_txn.exclude_from_reports = True
            
            # Case A: User selected an EXISTING transaction to link (Manual Match)
            if update_data.get('linked_transaction_id'):
                # 1. Unlink any old one
                if db_txn.linked_transaction_id:
                     old_linked = db.query(models.Transaction).filter(models.Transaction.id == db_txn.linked_transaction_id).first()
                     # If the old one was auto-generated (same amount, diff sign, transfer category), maybe delete? 
                     # For safety, let's just unlink it. User can delete manually if needed.
                     if old_linked:
                        old_linked.linked_transaction_id = None
                        db.add(old_linked)

                # 2. Link the new target
                target_id = update_data['linked_transaction_id']
                target_txn = db.query(models.Transaction).filter(models.Transaction.id == target_id).first()
                
                if target_txn:
                    db_txn.linked_transaction_id = target_txn.id
                    target_txn.linked_transaction_id = db_txn.id
                    target_txn.is_transfer = True
                    target_txn.category = "Transfer"
                    target_txn.exclude_from_reports = True # Ensure both are hidden
                    db.add(target_txn)

            # Case B: User selected an ACCOUNT to transfer to (Auto Create)
            elif to_account_id:
                if db_txn.linked_transaction_id:
                     old_linked = db.query(models.Transaction).filter(models.Transaction.id == db_txn.linked_transaction_id).first()
                     if old_linked: db.delete(old_linked)
                
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
                    linked_transaction_id=db_txn.id,
                    exclude_from_reports=True
                )
                db.add(target_txn)
                db_txn.linked_transaction_id = target_txn.id
                db_txn.category = "Transfer"
                update_data['category'] = "Transfer"

        elif is_transfer_update is False:
            db_txn.is_transfer = False
            if db_txn.linked_transaction_id:
                # If we are un-marking transfer, check if the linked txn was auto-generated
                linked = db.query(models.Transaction).filter(models.Transaction.id == db_txn.linked_transaction_id).first()
                if linked:
                    # HEURISTIC: If linked txn is also "Transfer" and "Hidden", unlink it. 
                    # If it looks like a manual match, just unlink. 
                    # If it looks like auto-gen, maybe delete? 
                    # Safest is just to unlink and let user clean up. 
                    linked.linked_transaction_id = None
                    linked.is_transfer = False # Should we reset? Maybe.
                    db.add(linked)

                db_txn.linked_transaction_id = None
        
        for key, value in update_data.items():
            if key in ['is_transfer', 'to_account_id']: continue
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
    def get_pending_transactions(db: Session, tenant_id: str, skip: int = 0, limit: int = 50):
        query = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        )
        total = query.count()
        items = query.order_by(ingestion_models.PendingTransaction.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    @staticmethod
    def approve_pending_transaction(
        db: Session, 
        pending_id: str, 
        tenant_id: str, 
        category_override: Optional[str] = None,
        is_transfer_override: bool = False,
        to_account_id_override: Optional[str] = None,
        exclude_from_reports_override: Optional[bool] = None,
        create_rule: bool = False
    ):
        pending = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.id == pending_id,
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).first()
        if not pending: return None
        
        final_is_transfer = is_transfer_override or pending.is_transfer
        final_to_account_id = to_account_id_override or pending.to_account_id
        final_category = category_override or pending.category or "Uncategorized"
        final_exclude = exclude_from_reports_override if exclude_from_reports_override is not None else pending.exclude_from_reports
        
        # Sync exclude if it was forced to transfer here
        if is_transfer_override:
            final_exclude = True
        
        if create_rule and pending.description:
            rule_create = schemas.CategoryRuleCreate(
                name=f"Rule for {pending.description[:20]}...",
                category=final_category,
                keywords=[pending.description],
                is_transfer=final_is_transfer,
                to_account_id=final_to_account_id,
                priority=10
            )
            CategoryService.create_category_rule(db, rule_create, tenant_id)

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
            tags=[],
            exclude_from_reports=final_exclude
        )
        
        if txn_create.is_transfer and txn_create.to_account_id:
            pending.is_transfer = final_is_transfer
            pending.to_account_id = final_to_account_id
            pending.exclude_from_reports = final_exclude
            real_txn = TransferService.approve_transfer(db, pending, tenant_id)
        else:
            real_txn = TransactionService.create_transaction(db, txn_create, tenant_id)
        
        if pending.balance is not None or pending.credit_limit is not None:
            account = db.query(models.Account).filter(models.Account.id == pending.account_id).first()
            if account:
                if pending.balance is not None:
                    account.balance = pending.balance
                if pending.credit_limit is not None:
                    account.credit_limit = pending.credit_limit

        db.delete(pending)
        db.commit()
        return real_txn

    @staticmethod
    def reject_pending_transaction(db: Session, pending_id: str, tenant_id: str, create_ignore_rule: bool = False):
        pending = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.id == pending_id,
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).first()
        if not pending: return False
        
        if create_ignore_rule:
            pattern = pending.recipient or pending.description
            if pattern:
                # Check if already exists
                existing = db.query(ingestion_models.IgnoredPattern).filter(
                    ingestion_models.IgnoredPattern.tenant_id == tenant_id,
                    ingestion_models.IgnoredPattern.pattern == pattern
                ).first()
                if not existing:
                    new_ignore = ingestion_models.IgnoredPattern(
                        tenant_id=tenant_id,
                        pattern=pattern,
                        source=pending.source
                    )
                    db.add(new_ignore)

        db.delete(pending)
        db.commit()
        return True

    @staticmethod
    def bulk_reject_pending_transactions(db: Session, pending_ids: List[str], tenant_id: str, create_ignore_rules: bool = False):
        if not pending_ids: return 0
        
        if create_ignore_rules:
            pendings = db.query(ingestion_models.PendingTransaction).filter(
                ingestion_models.PendingTransaction.id.in_(pending_ids),
                ingestion_models.PendingTransaction.tenant_id == tenant_id
            ).all()
            for p in pendings:
                pattern = p.recipient or p.description
                if pattern:
                    existing = db.query(ingestion_models.IgnoredPattern).filter(
                        ingestion_models.IgnoredPattern.tenant_id == tenant_id,
                        ingestion_models.IgnoredPattern.pattern == pattern
                    ).first()
                    if not existing:
                        new_ignore = ingestion_models.IgnoredPattern(
                            tenant_id=tenant_id,
                            pattern=pattern,
                            source=p.source
                        )
                        db.add(new_ignore)
        
        count = db.query(ingestion_models.PendingTransaction).filter(
            ingestion_models.PendingTransaction.id.in_(pending_ids),
            ingestion_models.PendingTransaction.tenant_id == tenant_id
        ).delete(synchronize_session=False)
        db.commit()
        return count

    @staticmethod
    def batch_update_category_and_create_rule(
        db: Session, 
        txn_id: str, 
        category: str, 
        tenant_id: str,
        create_rule: bool = False,
        apply_to_similar: bool = False,
        exclude_from_reports: bool = False
    ) -> dict:
        db_txn = db.query(models.Transaction).filter(
            models.Transaction.id == txn_id,
            models.Transaction.tenant_id == tenant_id
        ).first()
        
        if not db_txn:
            return {"success": False, "message": "Transaction not found"}
            
        old_category = db_txn.category
        db_txn.category = category
        if exclude_from_reports:
            db_txn.exclude_from_reports = True
        db.add(db_txn)
        
        affected_count = 1
        rule_created = False
        
        pattern = db_txn.recipient or db_txn.description
        if not pattern:
            db.commit()
            return {"success": True, "affected": affected_count, "rule_created": False}

        if create_rule:
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
                    priority=1,
                    exclude_from_reports=exclude_from_reports
                )
                db.add(new_rule)
                rule_created = True
            else:
                # Update existing rule to reflect new decision
                existing_rule.category = category
                existing_rule.exclude_from_reports = exclude_from_reports
                db.add(existing_rule)
                rule_created = True

        if apply_to_similar:
            query = db.query(models.Transaction).filter(
                models.Transaction.tenant_id == tenant_id,
                models.Transaction.id != txn_id,
                (models.Transaction.category == "Uncategorized") | (models.Transaction.category == None)
            )
            
            if db_txn.recipient:
                query = query.filter(models.Transaction.recipient == db_txn.recipient)
            else:
                query = query.filter(models.Transaction.description == db_txn.description)
                
            similar_txns = query.all()
            for st in similar_txns:
                st.category = category
                if exclude_from_reports:
                    st.exclude_from_reports = True
                db.add(st)
                affected_count += 1

        db.commit()
        return {
            "success": True, 
            "affected": affected_count, 
            "rule_created": rule_created,
            "pattern": pattern
        }
