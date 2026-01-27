from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.finance import schemas
from backend.app.modules.finance.services.transaction_service import TransactionService

router = APIRouter()

@router.post("/transactions", response_model=schemas.TransactionRead)
def create_transaction(
    transaction: schemas.TransactionCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TransactionService.create_transaction(db, transaction, str(current_user.tenant_id))

@router.get("/transactions", response_model=schemas.TransactionPagination)
def read_transactions(
    account_id: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * limit
    items = TransactionService.get_transactions(
        db, str(current_user.tenant_id), account_id, skip, limit, start_date, end_date, 
        search=search, category=category, user_role=current_user.role
    )
    total = TransactionService.count_transactions(
        db, str(current_user.tenant_id), account_id, start_date, end_date, 
        search=search, category=category, user_role=current_user.role
    )
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": limit
    }

@router.post("/transactions/bulk-delete")
def bulk_delete_transactions(
    payload: schemas.BulkDeleteRequest,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = TransactionService.bulk_delete_transactions(db, payload.transaction_ids, str(current_user.tenant_id))
    return {"message": f"Deleted {count} transactions", "count": count}

@router.put("/transactions/{transaction_id}", response_model=schemas.TransactionRead)
def update_transaction(
    transaction_id: str,
    transaction_update: schemas.TransactionUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_txn = TransactionService.update_transaction(
        db, transaction_id, transaction_update, str(current_user.tenant_id)
    )
    if not db_txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_txn

@router.post("/transactions/smart-categorize")
def smart_categorize_transaction(
    payload: schemas.SmartCategorizeRequest,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TransactionService.batch_update_category_and_create_rule(
        db, 
        payload.transaction_id, 
        payload.category, 
        str(current_user.tenant_id),
        create_rule=payload.create_rule,
        apply_to_similar=payload.apply_to_similar,
        exclude_from_reports=payload.exclude_from_reports
    )
