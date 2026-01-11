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
    is_verified: bool = True

class AccountCreate(AccountBase):
    owner_id: Optional[UUID] = None
    owner_name: Optional[str] = None

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[AccountType] = None
    currency: Optional[str] = None
    account_mask: Optional[str] = None
    owner_name: Optional[str] = None
    balance: Optional[Decimal] = None
    is_verified: Optional[bool] = None

from typing import Optional, List, Union
# ...
class AccountRead(AccountBase):
    id: Union[UUID, str]
    tenant_id: Union[UUID, str]
    owner_id: Optional[Union[UUID, str]] = None
    owner_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    amount: Decimal
    date: datetime
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class TransactionCreate(TransactionBase):
    account_id: UUID
    external_id: Optional[str] = None

class TransactionUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    date: Optional[datetime] = None
    amount: Optional[Decimal] = None

class Transaction(TransactionBase):
    id: UUID
    tenant_id: UUID
    account_id: UUID
    type: TransactionType
    created_at: datetime

    class Config:
        orm_mode = True

class TransactionRead(TransactionBase):
    id: UUID
    account_id: UUID
    tenant_id: UUID

    class Config:
        from_attributes = True

class CategoryRuleBase(BaseModel):
    name: str
    category: str
    keywords: List[str]
    priority: int = 0

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

class CategoryBase(BaseModel):
    name: str
    icon: Optional[str] = "🏷️"

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None

class CategoryRead(CategoryBase):
    id: str
    tenant_id: str
    
    class Config:
        from_attributes = True
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
