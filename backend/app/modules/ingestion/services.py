import json
from sqlalchemy.orm import Session
from sqlalchemy import func
import hashlib
from typing import Optional, Dict, Any, List
from backend.app.modules.finance import models as finance_models
from backend.app.modules.finance.services.transaction_service import TransactionService
from backend.app.modules.finance import schemas as finance_schemas
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.modules.ingestion.base import ParsedTransaction
from backend.app.modules.ingestion.transfer_detector import TransferDetector

class IngestionService:
    @staticmethod
    def log_event(db: Session, tenant_id: str, event_type: str, status: str, message: Optional[str] = None, data: Optional[dict] = None, device_id: Optional[str] = None):
        """
        Log an ingestion event for auditing.
        """
        event = ingestion_models.IngestionEvent(
            tenant_id=tenant_id,
            device_id=device_id,
            event_type=event_type,
            status=status,
            message=message,
            data_json=json.dumps(data) if data else None
        )
        db.add(event)
        db.commit()

    @staticmethod
    def match_account(db: Session, tenant_id: str, mask: str) -> Optional[finance_models.Account]:
        """
        Find an account belonging to the tenant that ends with the given mask.
        Mask usually is 4 digits like "1234".
        """
        if not mask or len(mask) < 2:
            return None
            
        # Basic suffix match
        # DuckDB/SQLAlchemy 'like' or 'endswith'
        # We assume the mask in DB (e.g. "XX1234") ends with the SMS mask (e.g. "1234")
        # or simplified: just check if DB account_mask ends with the provided digits
        
        accounts = db.query(finance_models.Account).filter(
            finance_models.Account.tenant_id == tenant_id,
            finance_models.Account.account_mask != None
        ).all()
        
        for acc in accounts:
            if acc.account_mask and acc.account_mask.endswith(mask[-4:]):
                return acc
        return None

    @staticmethod
    def process_transaction(db: Session, tenant_id: str, parsed: ParsedTransaction, extra_data: Optional[dict] = None):
        """
        Process a parsed transaction: match account, save transaction.
        """
        account = None
        if parsed.account_mask:
            account = IngestionService.match_account(db, tenant_id, parsed.account_mask)
            
        if not account and parsed.account_mask:
            # Auto-Discovery: Create new untrusted account
            source_label = parsed.source if parsed.source else "Auto"
            account = finance_models.Account(
                tenant_id=tenant_id,
                name=f"Detected: {source_label} (XX{parsed.account_mask[-4:]})",
                type=finance_models.AccountType.BANK, # Default to Bank
                account_mask=parsed.account_mask[-4:], # Store last 4 digits
                is_verified=False,
                balance=0.0
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            
        if not account:
             # Fallback if no mask was present in SMS at all
             # For V1, we log/skip
             return {"status": "skipped", "reason": f"No account found and no mask in SMS"}
            
        # Create Transaction or Move to Triage
        
        # Determine amount sign
        final_amount = parsed.amount
        if parsed.type == "DEBIT":
            final_amount = -abs(parsed.amount)
        else:
            final_amount = abs(parsed.amount)

        # --- DEDUPLICATION CHECK ---
        from backend.app.modules.ingestion.deduplicator import TransactionDeduplicator
        message_hash = TransactionDeduplicator.generate_hash(
            tenant_id, str(account.id), parsed.date, final_amount, parsed.description, parsed.recipient
        )

        is_dup, reason, existing_id = TransactionDeduplicator.check_duplicate(db, tenant_id, parsed, str(account.id), final_amount)
        
        if is_dup:
            return {"status": "skipped", "reason": f"Deduplicated: {reason}", "deduplicated": True, "existing_id": existing_id}

        # --- IGNORE PATTERN CHECK ---
        check_text = f"{(parsed.recipient or '')} {(parsed.description or '')}".lower()
        ignored_patterns = db.query(ingestion_models.IgnoredPattern).filter(
            ingestion_models.IgnoredPattern.tenant_id == tenant_id
        ).all()
        for ip in ignored_patterns:
            if ip.pattern.lower() in check_text:
                return {"status": "skipped", "reason": f"Ignored by user pattern: {ip.pattern}"}
        
        
        # 1. Try to detect internal transfer
        all_accounts = db.query(finance_models.Account).filter(finance_models.Account.tenant_id == tenant_id).all()
        all_rules = db.query(finance_models.CategoryRule).filter(finance_models.CategoryRule.tenant_id == tenant_id).all()
        
        is_transfer, to_account_id = TransferDetector.detect(parsed.description, parsed.recipient, all_accounts, all_rules)
        
        # 2. Try to auto-categorize
        # Prioritize category from parser if available (e.g. from Learned Patterns)
        category = parsed.category
        
        if not category or category == "Uncategorized":
            category = TransactionService.get_suggested_category(db, tenant_id, parsed.description, parsed.recipient)
        
        # If it's a transfer, we force category to "Transfer" if it matches a transfer rule
        if is_transfer:
            category = "Transfer"
        
        # Auto-ingest if we have a real category
        # If the category came from the parser (not None), we treat it as high confidence
        is_auto_ingest = (category and category != "Uncategorized")
        
        if is_auto_ingest:
            # High confidence -> Directly to transactions
            txn_create = finance_schemas.TransactionCreate(
                account_id=str(account.id),
                amount=final_amount,
                date=parsed.date,
                description=parsed.description,
                recipient=parsed.recipient,
                category=category,
                external_id=parsed.ref_id,
                source=parsed.source,
                tags=[],
                latitude=extra_data.get("latitude") if extra_data else None,
                longitude=extra_data.get("longitude") if extra_data else None,
                location_name=None, # TODO: Reverse Geocoding
                content_hash=message_hash,
                is_transfer=is_transfer,
                to_account_id=to_account_id,
                exclude_from_reports=is_transfer
            )
            try:
                db_txn = TransactionService.create_transaction(db, txn_create, tenant_id)
                return {"status": "success", "transaction_id": db_txn.id, "account": account.name}
            except Exception as e:
                raise e
        else:
            # Low confidence -> Move to Triage
            pending = ingestion_models.PendingTransaction(
                tenant_id=tenant_id,
                account_id=str(account.id),
                amount=final_amount,
                date=parsed.date,
                description=parsed.description,
                recipient=parsed.recipient,
                category="Uncategorized",
                source=parsed.source,
                raw_message=parsed.raw_message,
                content_hash=message_hash,
                external_id=parsed.ref_id, # Store the ref_id for triage too!
                is_transfer=is_transfer,
                to_account_id=to_account_id,
                exclude_from_reports=is_transfer,
                balance=parsed.balance,
                credit_limit=parsed.credit_limit,
                latitude=extra_data.get("latitude") if extra_data else None,
                longitude=extra_data.get("longitude") if extra_data else None,
                location_name=None 
            )
            db.add(pending)
            db.commit()
            db.refresh(pending)
            return {"status": "triaged", "pending_id": pending.id, "account": account.name}

    @staticmethod
    def capture_unparsed(db: Session, tenant_id: str, source: str, raw_content: str, subject: Optional[str] = None, sender: Optional[str] = None):
        """
        Save a message that looks like a transaction but failed all parsers.
        """
        msg_hash = hashlib.md5(raw_content.encode()).hexdigest()

        # 1. Ignore Pattern Check
        check_text = f"{(subject or '')} {(raw_content or '')}".lower()
        ignored_patterns = db.query(ingestion_models.IgnoredPattern).filter(
            ingestion_models.IgnoredPattern.tenant_id == tenant_id
        ).all()
        for ip in ignored_patterns:
            if ip.pattern.lower() in check_text:
                return # Skip noise

        # 2. Check if already exists to avoid spam
        existing = db.query(ingestion_models.UnparsedMessage).filter(
            ingestion_models.UnparsedMessage.tenant_id == tenant_id,
            ingestion_models.UnparsedMessage.content_hash == msg_hash
        ).first()
        if existing: return
        
        msg = ingestion_models.UnparsedMessage(
            tenant_id=tenant_id,
            source=source,
            raw_content=raw_content,
            content_hash=msg_hash,
            subject=subject,
            sender=sender
        )
        db.add(msg)
        db.commit()
