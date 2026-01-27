from sqlalchemy.orm import Session
from backend.app.modules.finance.models import Transaction, TransactionType
from backend.app.modules.ingestion.models import PendingTransaction
import uuid
from datetime import datetime

class TransferService:
    """
    Modular logic for executing transfers between accounts.
    """
    
    @staticmethod
    def approve_transfer(db: Session, pending: PendingTransaction, tenant_id: str) -> Transaction:
        """
        Creates two linked transactions representing the transfer.
        Returns the primary (source) transaction.
        """
        if not pending.is_transfer or not pending.to_account_id:
            raise ValueError("Pending transaction is not marked as a transfer or missing destination account.")

        # 1. Create Source Transaction (Debit from original account)
        source_txn = Transaction(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            account_id=pending.account_id,
            amount=pending.amount,
            date=pending.date,
            description=f"Transfer to {pending.to_account_id} (Linked)",
            recipient=pending.recipient,
            category="Transfer",
            type=TransactionType.DEBIT if pending.amount < 0 else TransactionType.CREDIT,
            is_transfer=True,
            external_id=pending.external_id,
            source=pending.source,
            exclude_from_reports=pending.exclude_from_reports
        )
        
        # 2. Create Target Transaction (Mirror/Credit to destination account)
        target_txn = Transaction(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            account_id=pending.to_account_id,
            amount=-pending.amount, # Invert amount for destination
            date=pending.date,
            description=f"Transfer from {pending.account_id} (Linked)",
            recipient=pending.recipient,
            category="Transfer",
            type=TransactionType.CREDIT if pending.amount < 0 else TransactionType.DEBIT,
            is_transfer=True,
            external_id=f"LINKED-{pending.external_id}" if pending.external_id else None,
            source=pending.source,
            linked_transaction_id=source_txn.id,
            exclude_from_reports=pending.exclude_from_reports
        )
        
        # Link source back to target
        source_txn.linked_transaction_id = target_txn.id
        
        db.add(source_txn)
        db.add(target_txn)
        
        # We don't commit here, the parent service caller handles the transaction
        return source_txn
