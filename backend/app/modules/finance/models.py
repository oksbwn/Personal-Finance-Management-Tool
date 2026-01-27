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
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True) # None = Shared Family Account
    name = Column(String, nullable=False)
    type = Column(SqlEnum(AccountType), nullable=False)
    currency = Column(String, default="INR", nullable=False)
    account_mask = Column(String, nullable=True) # e.g. "XX1234" used for SMS matching
    balance = Column(Numeric(15, 2), default=0.0) # Current Balance or Consumed Limit
    credit_limit = Column(Numeric(15, 2), nullable=True) # For Credit Cards
    billing_day = Column(Numeric(2, 0), nullable=True) # 1-31
    due_day = Column(Numeric(2, 0), nullable=True) # 1-31
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
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    account_id = Column(String, nullable=False, index=True)  # No FK to avoid DuckDB constraint
    type = Column(SqlEnum(TransactionType), default=TransactionType.DEBIT, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False) # Precision for currency
    date = Column(DateTime, nullable=False, index=True)
    description = Column(String, nullable=True)
    recipient = Column(String, nullable=True) # Extracted merchant/payee name
    category = Column(String, nullable=True) # Keeping simple string for now, could be FK later
    tags = Column(String, nullable=True) # JSON Array string
    content_hash = Column(String, nullable=True, index=True)
    external_id = Column(String, nullable=True) # For de-duplication
    is_transfer = Column(Boolean, default=False, nullable=False)
    linked_transaction_id = Column(String, nullable=True) # ID of the other leg of a transfer
    source = Column(String, default="MANUAL", nullable=False) # MANUAL, CSV, EXCEL, etc.
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    location_name = Column(String, nullable=True)
    exclude_from_reports = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    linked_transaction = relationship("Transaction", 
        remote_side=[id],
        primaryjoin="Transaction.linked_transaction_id==Transaction.id",
        foreign_keys=[linked_transaction_id],
        uselist=False,
        post_update=True
    )

    @property
    def transfer_account_id(self):
        if self.linked_transaction:
            return self.linked_transaction.account_id
        return None

    account = relationship("Account", back_populates="transactions",
                          primaryjoin="Transaction.account_id == Account.id",
                          foreign_keys="Transaction.account_id",
                          viewonly=True,
                          sync_backref=False)


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False) # e.g. "Food Apps"
    category = Column(String, nullable=False) # Target Category e.g. "Food"
    keywords = Column(String, nullable=False) # JSON List of strings e.g. '["Zomato", "Swiggy"]'
    priority = Column(Numeric(5,0), default=0) # Higher priority runs first
    is_transfer = Column(Boolean, default=False, nullable=False)
    to_account_id = Column(String, nullable=True) # Destination Account ID if it's a transfer rule
    exclude_from_reports = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class IgnoredSuggestion(Base):
    __tablename__ = "ignored_suggestions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    pattern = Column(String, nullable=False) # The description/keyword to ignore
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, nullable=True) # Emoji or icon code
    color = Column(String, default="#3B82F6") # Hex color code
    type = Column(String, default="expense") # expense/income
    created_at = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    category = Column(String, nullable=False, index=True) # e.g. "Food"
    amount_limit = Column(Numeric(15, 2), nullable=False) # Monthly Limit
    period = Column(String, default="MONTHLY") # For future extensibility
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Frequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False) # e.g. "Netflix Subscription"
    amount = Column(Numeric(15, 2), nullable=False)
    type = Column(SqlEnum(TransactionType), default=TransactionType.DEBIT, nullable=False)
    category = Column(String, nullable=True)
    account_id = Column(String, nullable=False, index=True)
    
    frequency = Column(SqlEnum(Frequency), default=Frequency.MONTHLY, nullable=False)
    start_date = Column(DateTime, nullable=False)
    next_run_date = Column(DateTime, nullable=False, index=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    exclude_from_reports = Column(Boolean, default=False, nullable=False)
    last_run_date = Column(DateTime, nullable=True) # To track when it last ran
    created_at = Column(DateTime, default=datetime.utcnow)

class MutualFundsMeta(Base):
    __tablename__ = "mutual_funds_meta"

    scheme_code = Column(String, primary_key=True)
    scheme_name = Column(String, nullable=False)
    isin_growth = Column(String, nullable=True)
    isin_reinvest = Column(String, nullable=True)
    fund_house = Column(String, nullable=True)
    category = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

class MutualFundHolding(Base):
    __tablename__ = "mutual_fund_holdings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    scheme_code = Column(String, ForeignKey("mutual_funds_meta.scheme_code"), nullable=False, index=True)
    folio_number = Column(String, nullable=True)
    units = Column(Numeric(15, 4), default=0)
    average_price = Column(Numeric(15, 4), default=0)
    current_value = Column(Numeric(15, 2), nullable=True)
    last_nav = Column(Numeric(15, 4), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

class MutualFundOrder(Base):
    __tablename__ = "mutual_fund_orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    holding_id = Column(String, nullable=True, index=True)
    scheme_code = Column(String, ForeignKey("mutual_funds_meta.scheme_code"), nullable=False, index=True)
    type = Column(String, default="BUY", nullable=False) # BUY, SELL
    amount = Column(Numeric(15, 2), nullable=False)
    units = Column(Numeric(15, 4), nullable=False)
    nav = Column(Numeric(15, 4), nullable=False)
    order_date = Column(DateTime, nullable=False, index=True)
    folio_number = Column(String, nullable=True, index=True)
    status = Column(String, default="COMPLETED")
    external_id = Column(String, nullable=True)
    import_source = Column(String, default="MANUAL")
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PortfolioTimelineCache(Base):
    """Cache for portfolio timeline snapshots to avoid recalculating historical data"""
    __tablename__ = "portfolio_timeline_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    snapshot_date = Column(DateTime, nullable=False, index=True)  # Date of this snapshot
    portfolio_hash = Column(String, nullable=False, index=True)  # Hash of scheme_codes to detect changes
    portfolio_value = Column(Numeric(15, 2), nullable=False)
    invested_value = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for fast lookups
    __table_args__ = (
        {'sqlite_autoincrement': True}
    )