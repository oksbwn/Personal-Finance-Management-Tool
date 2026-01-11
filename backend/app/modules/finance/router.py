from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.finance import schemas, services

router = APIRouter()

# --- Accounts ---
@router.post("/accounts", response_model=schemas.AccountRead)
def create_account(
    account: schemas.AccountCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new account for the current tenant.
    """
    if account.owner_id is None:
        account.owner_id = current_user.id # Default to current user if not specified? Or leave None for shared?
        # Let's say explicit None means shared, but we need to ensure UUID type
        pass
    
    return services.FinanceService.create_account(db, account, str(current_user.tenant_id))

@router.get("/accounts", response_model=List[schemas.AccountRead])
def read_accounts(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List accounts for the tenant.
    """
    return services.FinanceService.get_accounts(db, str(current_user.tenant_id))

@router.put("/accounts/{account_id}", response_model=schemas.AccountRead)
def update_account(
    account_id: str,
    account_update: schemas.AccountUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing account.
    """
    db_account = services.FinanceService.update_account(
        db, account_id, account_update, str(current_user.tenant_id)
    )
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")
    return db_account

# --- Transactions ---
@router.post("/transactions", response_model=schemas.TransactionRead)
def create_transaction(
    transaction: schemas.TransactionCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record a new transaction.
    """
    return services.FinanceService.create_transaction(db, transaction, str(current_user.tenant_id))

@router.get("/transactions", response_model=List[schemas.TransactionRead])
def read_transactions(
    account_id: Optional[str] = None,
    limit: int = 100,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List transactions.
    """
    """
    List transactions.
    """
    return services.FinanceService.get_transactions(db, str(current_user.tenant_id), account_id, limit)

@router.put("/transactions/{transaction_id}", response_model=schemas.TransactionRead)
def update_transaction(
    transaction_id: str,
    transaction_update: schemas.TransactionUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a transaction (e.g. set category).
    """
    db_txn = services.FinanceService.update_transaction(
        db, transaction_id, transaction_update, str(current_user.tenant_id)
    )
    if not db_txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_txn

@router.get("/metrics")
def get_metrics(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Net Worth and Monthly Spending.
    """
    return services.FinanceService.get_summary_metrics(db, str(current_user.tenant_id))

# --- Rules ---
@router.post("/rules", response_model=schemas.CategoryRuleRead)
def create_rule(
    rule: schemas.CategoryRuleCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new auto-categorization rule.
    """
    return services.FinanceService.create_category_rule(db, rule, str(current_user.tenant_id))

@router.get("/rules", response_model=List[schemas.CategoryRuleRead])
def get_rules(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all auto-categorization rules.
    """
    return services.FinanceService.get_category_rules(db, str(current_user.tenant_id))

@router.get("/rules/suggestions", response_model=List[schemas.RuleSuggestion])
def get_rule_suggestions(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get suggested rules based on transaction history.
    """
    return services.FinanceService.get_rule_suggestions(db, str(current_user.tenant_id))

@router.put("/rules/{rule_id}", response_model=schemas.CategoryRuleRead)
def update_rule(
    rule_id: str,
    rule_update: schemas.CategoryRuleUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a rule.
    """
    db_rule = services.FinanceService.update_category_rule(db, rule_id, rule_update, str(current_user.tenant_id))
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return db_rule

@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a rule.
    """
    success = services.FinanceService.delete_category_rule(db, rule_id, str(current_user.tenant_id))
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "success"}

# --- Categories ---

@router.get("/categories", response_model=List[schemas.CategoryRead])
def get_categories(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return services.FinanceService.get_categories(db, str(current_user.tenant_id))

@router.post("/categories", response_model=schemas.CategoryRead)
def create_category(
    category: schemas.CategoryCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return services.FinanceService.create_category(db, category, str(current_user.tenant_id))

@router.put("/categories/{category_id}", response_model=schemas.CategoryRead)
def update_category(
    category_id: str,
    update: schemas.CategoryUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cat = services.FinanceService.update_category(db, category_id, update, str(current_user.tenant_id))
    if not cat: raise HTTPException(status_code=404, detail="Category not found")
    return cat

@router.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = services.FinanceService.delete_category(db, category_id, str(current_user.tenant_id))
    if not success: raise HTTPException(status_code=404, detail="Category not found")
    return {"status": "success"}

# --- Budgets ---
@router.get("/budgets", response_model=List[schemas.BudgetProgress])
def get_budgets(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all budgets with spending progress for the current month.
    """
    return services.FinanceService.get_budgets(db, str(current_user.tenant_id))

@router.post("/budgets", response_model=schemas.BudgetRead)
def set_budget(
    budget: schemas.BudgetCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set (Create or Update) a budget for a category.
    """
    return services.FinanceService.set_budget(db, budget, str(current_user.tenant_id))

@router.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a budget.
    """
    success = services.FinanceService.delete_budget(db, budget_id, str(current_user.tenant_id))
    if not success:
        raise HTTPException(status_code=404, detail="Budget not found")
    return {"status": "success"}
