import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
import enum

class AccountType(str, enum.Enum):
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    LOAN = "LOAN"
    WALLET = "WALLET"
    INVESTMENT = "INVESTMENT"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True) # None = Shared Family Account
    name = Column(String, nullable=False)
    type = Column(SqlEnum(AccountType), nullable=False)
    currency = Column(String, default="INR", nullable=False)
    account_mask = Column(String, nullable=True) # e.g. "XX1234" used for SMS matching
    balance = Column(Numeric(15, 2), default=0.0) # Current Balance or Consumed Limit
    credit_limit = Column(Numeric(15, 2), nullable=True) # For Credit Cards
    is_verified = Column(Boolean, default=True, nullable=False) # False = Auto-detected from SMS
    import_config = Column(String, nullable=True) # JSON config for CSV/Excel mapping
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan",
                               primaryjoin="Account.id == Transaction.account_id",
                               foreign_keys="Transaction.account_id",
                               viewonly=True,
                               sync_backref=False)



class TransactionType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    account_id = Column(String, nullable=False)  # No FK to avoid DuckDB constraint
    type = Column(SqlEnum(TransactionType), default=TransactionType.DEBIT, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False) # Precision for currency
    date = Column(DateTime, nullable=False)
    description = Column(String, nullable=True)
    recipient = Column(String, nullable=True) # Extracted merchant/payee name
    category = Column(String, nullable=True) # Keeping simple string for now, could be FK later
    tags = Column(String, nullable=True) # JSON Array string
    external_id = Column(String, nullable=True) # For de-duplication
    source = Column(String, default="MANUAL", nullable=False) # MANUAL, CSV, EXCEL, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions",
                          primaryjoin="Transaction.account_id == Account.id",
                          foreign_keys="Transaction.account_id",
                          viewonly=True,
                          sync_backref=False)


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False) # e.g. "Food Apps"
    category = Column(String, nullable=False) # Target Category e.g. "Food"
    keywords = Column(String, nullable=False) # JSON List of strings e.g. '["Zomato", "Swiggy"]'
    priority = Column(Numeric(5,0), default=0) # Higher priority runs first
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    icon = Column(String, nullable=True) # Emoji or icon code
    created_at = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    category = Column(String, nullable=False) # e.g. "Food"
    amount_limit = Column(Numeric(15, 2), nullable=False) # Monthly Limit
    period = Column(String, default="MONTHLY") # For future extensibility
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
