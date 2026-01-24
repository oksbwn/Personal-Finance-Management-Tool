from pydantic import BaseModel
from typing import Optional, List, Union
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from backend.app.modules.finance.models import AccountType, TransactionType

class AccountBase(BaseModel):
    name: str
    type: AccountType
    currency: str = "INR"
    account_mask: Optional[str] = None
    balance: Optional[Decimal] = 0.0
    credit_limit: Optional[Decimal] = None
    billing_day: Optional[int] = None
    due_day: Optional[int] = None
    is_verified: bool = True
    import_config: Optional[str] = None

class AccountCreate(AccountBase):
    owner_id: Optional[UUID] = None

    tenant_id: Optional[Union[UUID, str]] = None # Allow specifying a tenant

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[AccountType] = None
    currency: Optional[str] = None
    account_mask: Optional[str] = None

    owner_id: Optional[UUID] = None
    balance: Optional[Decimal] = None
    credit_limit: Optional[Decimal] = None
    billing_day: Optional[int] = None
    due_day: Optional[int] = None
    is_verified: Optional[bool] = None
    import_config: Optional[str] = None
    tenant_id: Optional[Union[UUID, str]] = None

from typing import Optional, List, Union
# ...
class AccountRead(AccountBase):
    id: Union[UUID, str]
    tenant_id: Union[UUID, str]
    owner_id: Optional[Union[UUID, str]] = None

    created_at: datetime

    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    amount: Decimal
    date: datetime
    description: Optional[str] = None
    recipient: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_transfer: bool = False
    linked_transaction_id: Optional[str] = None

class TransactionCreate(TransactionBase):
    account_id: UUID
    external_id: Optional[str] = None
    source: Optional[str] = "MANUAL"
    is_transfer: bool = False
    to_account_id: Optional[str] = None

class TransactionUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    date: Optional[datetime] = None
    amount: Optional[Decimal] = None
    is_transfer: Optional[bool] = None
    to_account_id: Optional[str] = None

class Transaction(TransactionBase):
    id: UUID
    tenant_id: UUID
    account_id: UUID
    type: TransactionType
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionRead(TransactionBase):
    id: UUID
    account_id: UUID
    tenant_id: UUID
    type: Optional[str] = "DEBIT"
    source: Optional[str] = "MANUAL"
    external_id: Optional[str] = None
    transfer_account_id: Optional[UUID] = None

    class Config:
        from_attributes = True

class TransactionPagination(BaseModel):
    items: List[TransactionRead]
    total: int
    page: int
    size: int

class BulkDeleteRequest(BaseModel):
    transaction_ids: List[str]


class CategoryRuleBase(BaseModel):
    name: str
    category: str
    keywords: List[str]
    priority: int = 0
    is_transfer: bool = False
    to_account_id: Optional[str] = None

class CategoryRuleCreate(CategoryRuleBase):
    pass

class CategoryRuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[List[str]] = None
    priority: Optional[int] = None

class CategoryRuleRead(CategoryRuleBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class RuleSuggestion(BaseModel):
    name: str
    category: str
    keywords: List[str]
    confidence: int

class IgnoredSuggestionCreate(BaseModel):
    pattern: str

class CategoryBase(BaseModel):
    name: str
    icon: Optional[str] = "🏷️"
    color: Optional[str] = "#3B82F6"

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

class CategoryRead(CategoryBase):
    id: str
    tenant_id: str
    
    class Config:
        from_attributes = True

class BudgetBase(BaseModel):
    category: str
    amount_limit: Decimal
    period: str = "MONTHLY"

class BudgetCreate(BudgetBase):
    pass

class BudgetUpdate(BaseModel):
    amount_limit: Optional[Decimal] = None

class BudgetRead(BudgetBase):
    id: UUID
    tenant_id: UUID
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BudgetProgress(BudgetRead):
    spent: Decimal
    remaining: Decimal
    percentage: float

class SmartCategorizeRequest(BaseModel):
    transaction_id: str
    category: str
    create_rule: bool = False
    apply_to_similar: bool = False

class Frequency(str): 
    # Helper for frontend types, though we validated via Enum in models
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class RecurringTransactionBase(BaseModel):
    name: str
    amount: Decimal
    account_id: UUID
    category: Optional[str] = None
    frequency: str = "MONTHLY" 
    start_date: datetime
    next_run_date: datetime
    is_active: bool = True

class RecurringTransactionCreate(RecurringTransactionBase):
    pass

class RecurringTransactionUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    account_id: Optional[UUID] = None
    category: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[datetime] = None
    next_run_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class RecurringTransactionRead(RecurringTransactionBase):
    id: UUID
    tenant_id: UUID
    last_run_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True