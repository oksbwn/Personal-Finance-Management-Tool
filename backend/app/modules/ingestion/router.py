from typing import List, Dict, Optional
from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import get_db

from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user

from backend.app.modules.finance import schemas as finance_schemas
from backend.app.modules.finance.services.transaction_service import TransactionService

from backend.app.modules.ingestion.services import IngestionService
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.modules.ingestion.pattern_service import PatternGenerator
from backend.app.modules.ingestion.email_sync import EmailSyncService
from backend.app.modules.ingestion.registry import SmsParserRegistry, EmailParserRegistry
from backend.app.modules.ingestion.parsers.hdfc import HdfcSmsParser, HdfcEmailParser
from backend.app.modules.ingestion.parsers.generic import GenericSmsParser, GenericEmailParser
from backend.app.modules.ingestion.parsers.icici import IciciSmsParser, IciciEmailParser
from backend.app.modules.ingestion.parsers.axis import AxisSmsParser, AxisEmailParser
from backend.app.modules.ingestion.parsers.sbi import SbiSmsParser, SbiEmailParser
from backend.app.modules.ingestion.parsers.kotak import KotakSmsParser, KotakEmailParser
from backend.app.modules.ingestion.parsers.universal_parser import UniversalParser

router = APIRouter(tags=["Ingestion"])

# Register Parsers
SmsParserRegistry.register(HdfcSmsParser())
SmsParserRegistry.register(GenericSmsParser())
SmsParserRegistry.register(IciciSmsParser())
SmsParserRegistry.register(AxisSmsParser())
SmsParserRegistry.register(SbiSmsParser())
SmsParserRegistry.register(KotakSmsParser())
EmailParserRegistry.register(HdfcEmailParser())
EmailParserRegistry.register(GenericEmailParser())
EmailParserRegistry.register(IciciEmailParser())
EmailParserRegistry.register(AxisEmailParser())
EmailParserRegistry.register(SbiEmailParser())
EmailParserRegistry.register(KotakEmailParser())


class SmsPayload(BaseModel):
    sender: str
    message: str

class EmailPayload(BaseModel):
    subject: str
    body: str

class EmailSyncPayload(BaseModel):
    imap_server: str = "imap.gmail.com"
    email: str
    password: str # App Password recommended
    folder: str = "INBOX"
    unread_only: bool = True

class EmailConfigCreate(BaseModel):
    email: str
    password: str
    imap_server: str = "imap.gmail.com"
    folder: str = "INBOX"
    auto_sync_enabled: bool = False
    user_id: Optional[str] = None

class EmailConfigUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    imap_server: Optional[str] = None
    folder: Optional[str] = None
    auto_sync_enabled: Optional[bool] = None
    user_id: Optional[str] = None
    reset_sync_history: Optional[bool] = False
    last_sync_at: Optional[datetime] = None

class EmailSyncLogRead(BaseModel):
    id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    items_processed: float
    message: Optional[str]
    
    class Config:
        from_attributes = True

class EmailConfigRead(EmailConfigCreate):
    id: str
    is_active: bool
    auto_sync_enabled: bool = False
    last_sync_at: Optional[datetime] = None

@router.post("/sms")
def ingest_sms(
    payload: SmsPayload,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest a raw SMS message, parse it, and SAVE the transaction if account matches.
    """
    parsed = SmsParserRegistry.parse(payload.sender, payload.message)
    
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse SMS content")
        
    result = IngestionService.process_transaction(db, str(current_user.tenant_id), parsed)
    
    return {
        "status": "processed",
        "parsed_data": parsed,
        "result": result
    }

@router.post("/email")
def ingest_email(
    payload: EmailPayload,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest a raw Email, parse it, and SAVE the transaction if account matches.
    """
    parsed = EmailParserRegistry.parse(payload.subject, payload.body)
    
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse Email content")
        
    result = IngestionService.process_transaction(db, str(current_user.tenant_id), parsed)
    
    return {
        "status": "processed",
        "parsed_data": parsed,
        "result": result
    }

@router.post("/email/sync")
def sync_email_inbox(
    payload: EmailSyncPayload,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Connect to IMAP and scan for transactions.
    """
    search_crit = 'UNSEEN' if payload.unread_only else 'ALL'
    
    result = EmailSyncService.sync_emails(
        db=db,
        tenant_id=str(current_user.tenant_id),
        imap_server=payload.imap_server,
        email_user=payload.email,
        email_pass=payload.password,
        folder=payload.folder,
        search_criterion=search_crit
    )
    
    return result

@router.get("/email/configs", response_model=List[EmailConfigRead])
def list_email_configs(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ingestion_models.EmailConfiguration).filter(
        ingestion_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    ).all()

@router.post("/email/configs", response_model=EmailConfigRead)
def create_email_config(
    payload: EmailConfigCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = ingestion_models.EmailConfiguration(
        tenant_id=str(current_user.tenant_id),
        **payload.dict()
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

@router.put("/email/configs/{config_id}", response_model=EmailConfigRead)
def update_email_config(
    config_id: str,
    payload: EmailConfigUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = db.query(ingestion_models.EmailConfiguration).filter(
        ingestion_models.EmailConfiguration.id == config_id,
        ingestion_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Update fields
    if payload.email is not None: config.email = payload.email
    if payload.password is not None: config.password = payload.password
    if payload.imap_server is not None: config.imap_server = payload.imap_server
    if payload.folder is not None: config.folder = payload.folder
    if payload.user_id is not None: config.user_id = payload.user_id

    if payload.auto_sync_enabled is not None: config.auto_sync_enabled = payload.auto_sync_enabled
    if payload.reset_sync_history:
        config.last_sync_at = None
    if payload.last_sync_at is not None:
        config.last_sync_at = payload.last_sync_at
    
    db.commit()
    db.refresh(config)
    return config

@router.delete("/email/configs/{config_id}")
def delete_email_config(
    config_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = db.query(ingestion_models.EmailConfiguration).filter(
        ingestion_models.EmailConfiguration.id == config_id,
        ingestion_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
    return {"status": "deleted"}

@router.get("/email/configs/{config_id}/logs", response_model=List[EmailSyncLogRead])
def get_email_sync_logs(
    config_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify ownership
    config = db.query(ingestion_models.EmailConfiguration).filter(
        ingestion_models.EmailConfiguration.id == config_id,
        ingestion_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    return db.query(ingestion_models.EmailSyncLog).filter(
        ingestion_models.EmailSyncLog.config_id == config_id
    ).order_by(ingestion_models.EmailSyncLog.started_at.desc()).limit(10).all()

@router.post("/email/sync/{config_id}")
def sync_specific_email(
    config_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = db.query(ingestion_models.EmailConfiguration).filter(
        ingestion_models.EmailConfiguration.id == config_id,
        ingestion_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    criterion = 'ALL' 
    
    result = EmailSyncService.sync_emails(
        db=db,
        tenant_id=str(current_user.tenant_id),
        config_id=config.id,
        imap_server=config.imap_server,
        email_user=config.email,
        email_pass=config.password,
        folder=config.folder,
        search_criterion=criterion,
        since_date=config.last_sync_at
    )
    
    if result.get("status") == "completed":
        config.last_sync_at = datetime.utcnow()
        db.commit()
        
    return result

@router.post("/csv/analyze")

async def analyze_file(
    file: UploadFile = File(...),
    current_user: auth_models.User = Depends(get_current_user)
):
    """
    Auto-detect header row and return preview.
    """
    try:
        content = await file.read()
        analysis = UniversalParser.analyze(content, file.filename)
        return analysis
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/csv/parse") 
async def parse_file(
    file: UploadFile = File(...),
    mapping: str = Form(...), # JSON string
    header_row_index: int = Form(0),
    current_user: auth_models.User = Depends(get_current_user)
):
    """
    Parse CSV/Excel and return rows.
    """
    try:
        mapping_dict = json.loads(mapping)
        content = await file.read()
        # Pass filename to detect extension
        parsed = UniversalParser.parse(content, file.filename, mapping_dict, header_row_index)
        return parsed
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

class ImportItem(BaseModel):
    date: str
    description: str
    recipient: Optional[str] = None
    amount: float
    type: str # DEBIT/CREDIT
    external_id: Optional[str] = None
    balance: Optional[float] = None
    credit_limit: Optional[float] = None
    is_transfer: bool = False
    to_account_id: Optional[str] = None

class ImportPayload(BaseModel):
    account_id: str
    transactions: List[ImportItem]
    source: str = "CSV" # Default to CSV

@router.post("/csv/import")
def import_csv(
    payload: ImportPayload,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk import verified transactions.
    """
    success_count = 0
    errors = []
    
    from datetime import datetime
    
    for idx, txn in enumerate(payload.transactions):
        try:
             # Convert to Finance Service format
             # Note: Parser already returns negative amounts for DEBIT, positive for CREDIT
             txn_create = finance_schemas.TransactionCreate(
                 account_id=payload.account_id,
                 amount=txn.amount,  # Use parsed amount as-is
                 date=datetime.fromisoformat(txn.date),
                 description=txn.description,
                 recipient=txn.recipient,  # Extracted merchant/payee
                 category="Uncategorized",
                 tags=[],
                 source=payload.source,
                 external_id=txn.external_id
             )
             TransactionService.create_transaction(db, txn_create, str(current_user.tenant_id))
             success_count += 1
        except Exception as e:
            errors.append(f"Row {idx+1}: {str(e)}")
            
    return {
        "status": "completed",
        "imported": success_count,
        "errors": errors
    }

# --- Triage Area ---

class PendingTransactionRead(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    amount: float
    date: datetime
    description: Optional[str] = None
    recipient: Optional[str] = None
    category: Optional[str] = None
    source: str
    raw_message: Optional[str] = None
    external_id: Optional[str] = None
    balance: Optional[float] = None
    credit_limit: Optional[float] = None
    is_transfer: bool = False
    to_account_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/triage", response_model=List[PendingTransactionRead])
def list_triage(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TransactionService.get_pending_transactions(db, str(current_user.tenant_id))

class TriageApproveRequest(BaseModel):
    category: Optional[str] = None
    is_transfer: bool = False
    to_account_id: Optional[str] = None
    create_rule: bool = False

@router.post("/triage/{pending_id}/approve")
def approve_triage(
    pending_id: str,
    payload: TriageApproveRequest,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    txn = TransactionService.approve_pending_transaction(
        db, 
        pending_id, 
        str(current_user.tenant_id), 
        category_override=payload.category,
        is_transfer_override=payload.is_transfer,
        to_account_id_override=payload.to_account_id,
        create_rule=payload.create_rule
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")
    return {"status": "approved", "transaction_id": txn.id}

@router.delete("/triage/{pending_id}")
def reject_triage(
    pending_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = TransactionService.reject_pending_transaction(db, pending_id, str(current_user.tenant_id))
    if not success:
        raise HTTPException(status_code=404, detail="Pending transaction not found")
    return {"status": "rejected"}

# --- Interactive Training ---

class UnparsedMessageRead(BaseModel):
    id: str
    source: str
    raw_content: str
    subject: Optional[str]
    sender: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/training", response_model=List[UnparsedMessageRead])
def list_training_messages(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ingestion_models.UnparsedMessage).filter(
        ingestion_models.UnparsedMessage.tenant_id == str(current_user.tenant_id)
    ).order_by(ingestion_models.UnparsedMessage.created_at.desc()).all()

class LabelPayload(BaseModel):
    amount: float
    date: datetime
    account_mask: str
    recipient: Optional[str]
    ref_id: Optional[str]
    generate_pattern: bool = True

@router.post("/training/{message_id}/label")
def label_message(
    message_id: str,
    payload: LabelPayload,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = db.query(ingestion_models.UnparsedMessage).filter(
        ingestion_models.UnparsedMessage.id == message_id,
        ingestion_models.UnparsedMessage.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Promote to PendingTransaction
    account = IngestionService.match_account(db, str(current_user.tenant_id), payload.account_mask)
    if not account:
        # Create auto-account if mask provided
        account = finance_models.Account(
            tenant_id=str(current_user.tenant_id),
            name=f"Detected: (XX{payload.account_mask[-4:]})",
            type=finance_models.AccountType.BANK,
            account_mask=payload.account_mask[-4:],
            is_verified=False,
            balance=0.0
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    effective_ref = payload.ref_id
    if not effective_ref:
        date_str = payload.date.strftime("%Y%m%d%H%M%S")
        effective_ref = f"MAN-{date_str}-{payload.account_mask}-{payload.amount:.2f}"

    pending = ingestion_models.PendingTransaction(
        tenant_id=str(current_user.tenant_id),
        account_id=str(account.id),
        amount=payload.amount,
        date=payload.date,
        description=f"Labeled: {payload.recipient or 'Unknown'}",
        recipient=payload.recipient,
        category="Uncategorized",
        source=msg.source,
        raw_message=msg.raw_content,
        external_id=effective_ref
    )
    db.add(pending)
    
    # Pattern Generation Logic
    if payload.generate_pattern:
        try:
            pattern_str, mapping_json = PatternGenerator.generate_regex_and_config(msg.raw_content, payload.dict())
            new_pattern = ingestion_models.ParsingPattern(
                tenant_id=str(current_user.tenant_id),
                pattern_type=msg.source,
                pattern_value=pattern_str,
                mapping_config=mapping_json,
                is_active=True,
                description=f"Auto-learned from: {payload.recipient or 'Unknown'}"
            )
            db.add(new_pattern)
            print(f"[Training] Generated new pattern: {pattern_str}")
        except Exception as e:
            print(f"[Training] Failed to generate pattern: {e}")
        
    db.delete(msg)
    db.commit()
    
    return {"status": "labeled", "pending_id": pending.id}

@router.delete("/training/{message_id}")
def dismiss_training_message(
    message_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = db.query(ingestion_models.UnparsedMessage).filter(
        ingestion_models.UnparsedMessage.id == message_id,
        ingestion_models.UnparsedMessage.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    db.delete(msg)
    db.commit()
    return {"status": "dismissed"}
