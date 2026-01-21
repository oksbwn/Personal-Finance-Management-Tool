import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship, foreign, remote
from backend.app.core.database import Base

class EmailConfiguration(Base):
    __tablename__ = "email_configurations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # Link to family member
    email = Column(String, nullable=False)
    # Note: In a real app, encrypt this. For now, storing as-is.
    password = Column(String, nullable=False) 
    imap_server = Column(String, default="imap.gmail.com", nullable=False)
    folder = Column(String, default="INBOX", nullable=False)
    is_active = Column(Boolean, default=True)
    auto_sync_enabled = Column(Boolean, default=False)
    last_sync_at = Column(DateTime, nullable=True) # General expense sync
    cas_last_sync_at = Column(DateTime, nullable=True) # Mutual fund CAS sync
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailSyncLog(Base):
    __tablename__ = "email_sync_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(String, ForeignKey("email_configurations.id"), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running") # running, completed, error
    items_processed = Column(Numeric(10, 0), default=0)
    message = Column(String, nullable=True) # JSON or text log

class PendingTransaction(Base):
    __tablename__ = "pending_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    account_id = Column(String, nullable=False)  # No FK for DuckDB compliance
    
    # Relationships
    account = relationship("Account", 
                          primaryjoin="PendingTransaction.account_id == foreign(remote(Account.id))",
                          viewonly=True,
                          sync_backref=False,
                          overlaps="account")
    amount = Column(Numeric(15, 2), nullable=False)
    date = Column(DateTime, nullable=False)
    description = Column(String, nullable=True)
    recipient = Column(String, nullable=True)
    category = Column(String, nullable=True)
    source = Column(String, nullable=False) # SMS, EMAIL
    raw_message = Column(String, nullable=True)
    external_id = Column(String, nullable=True) # Reference Number/UTR
    is_transfer = Column(Boolean, default=False, nullable=False)
    to_account_id = Column(String, nullable=True) # Destination Account ID for transfers
    balance = Column(Numeric(15, 2), nullable=True)
    credit_limit = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UnparsedMessage(Base):
    __tablename__ = "unparsed_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    source = Column(String, nullable=False) # SMS, EMAIL
    raw_content = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ParsingPattern(Base):
    __tablename__ = "parsing_patterns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    pattern_type = Column(String, default="regex") # regex, template
    pattern_value = Column(String, nullable=False) # The regex or template string
    mapping_config = Column(String, nullable=False) # JSON: { "amount": 1, "date": 2, ... }
    is_active = Column(Boolean, default=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AIConfiguration(Base):
    __tablename__ = "ai_configurations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    provider = Column(String, default="gemini") # gemini, openai, etc.
    model_name = Column(String, default="gemini-pro")
    api_key = Column(String, nullable=True) # Sensitive
    is_enabled = Column(Boolean, default=True)
    
    # Store prompts as a JSON string to keep it agnostic and extensible
    # { "parsing": "...", "insights": "..." }
    prompts_json = Column(String, nullable=True) 
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AICallCache(Base):
    __tablename__ = "ai_call_cache"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    content_hash = Column(String, index=True, nullable=False)
    provider = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    response_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
